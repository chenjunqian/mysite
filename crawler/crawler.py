#coding=utf-8
import time
import json
import Zhihu
import re
from multiprocessing import Pool
from getpass import getpass
import logging
import MySQLdb
import requests
from bs4 import BeautifulSoup
import cookielib
import requests


class zhihu_crawler:

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        handle = logging.FileHandler('ZhihuCrawl.log')
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        formatter.converter = time.localtime
        handle.setFormatter(formatter)
        self.logger.addHandler(handle)

        self.connection = MySQLdb.connect(
            host='118.190.103.54',
            user='root',
            passwd='root',
            db='mysite',
            charset="utf8"
        )
        self.cursor = self.connection.cursor()
        self.zhihu_client = Zhihu.ZhihuClient(self.logger)
        # self.process_pool = Pool(processes=3)


    def main(self):
        try:
            input = raw_input
        except:
            pass

        if self.zhihu_client.is_login():
            self.run(self.zhihu_client)
        else:
            account = input('输入账号 \n > ')
            password = getpass("请输入登录密码: ")
            self.zhihu_client.login(account, password)
            if self.zhihu_client.is_login():
                self.run(self.zhihu_client)

    def run(self, zhihu_client):
        '''
            统一请求函数格式
            All the test or other method should call in this function
        '''
        # self.crawl_activities(zhihu_client)
        self.crawl_my_feed(zhihu_client)
        # self.voteup_activities(zhihu_client, '64245225')

        #####爬取用户动态#######
    def crawl_activities(self, zhihu_client):
        """
            爬取用户动态
            Get the activities of the user's home page
        """
        limit = 20
        #获取动态的时间戳 0 则是从现在开始获取
        #It starts from the begging when timestamp is 0
        start = 1473035448

        crawl_times = 0
        response = []

        while True:
            try:
                response = zhihu_client.get_more_activities(limit, start)
                print response
                json_response = json.loads(response)
            except requests.exceptions.ConnectionError:
                self.logger.exception('connection refused')
                print 'Catch activities connection refused, waiting for 120s......'
                time.sleep(120)
                continue
            except ValueError:
                self.logger.exception('Catch activities ValueError'+
                                      ' maybe No JSON object could be decoded')
                print 'Get activities error, waiting for 1200s, and then break......'
                time.sleep(1200)
                break
            except:
                self.logger.exception('Catch activities error')
                print 'Get activities error, waiting for 1200s, and then break......'
                time.sleep(1200)
                break

            limit = json_response['msg'][0]
            soup = BeautifulSoup(json_response['msg'][1], 'html.parser')
            activities = soup.find_all('div', class_='zm-profile-section-item zm-item clearfix')
            if len(activities) > 0:
                start = activities[-1]['data-time']
                self.logger.info('start time : '+str(start))

            for activity in activities:
                self.parse_activitis(zhihu_client, activity)

            # crawl_times = crawl_times + 1
            # if crawl_times == 10:
            #     self.logger.info('crawl activities 10 times, sleep 60s...')
            #     time.sleep(60)
            # elif crawl_times == 20:
            #     self.logger.info('crawl activities 20 times, sleep 80s...')
            #     time.sleep(80)
            # elif crawl_times == 30:
            #     self.logger.info('crawl activities 30 times, sleep 1200s...')
            #     crawl_times = 0
            #     time.sleep(1200)
            # else:
            #     self.logger.info('crawl activities, waiting for 20s...')
            #     time.sleep(20)

        def parse_response(response):
            limit = json_response['msg'][0]
            soup = BeautifulSoup(json_response['msg'][1], 'html.parser')
            activities = soup.find_all('div', class_='zm-profile-section-item zm-item clearfix')
            if len(activities) > 0:
                start = activities[-1]['data-time']
                self.logger.info('start time : '+str(start))

            for activity in activities:
                self.parse_activitis(zhihu_client, activity)


    def parse_activitis(self, zhihu_client, activity):
        '''
            根据不同的标签来判断用户动态的类型
            Base on the data type in the HTML file to parse the difference activities
        '''
        if activity.attrs['data-type-detail'] == 'member_voteup_answer':
            #赞同了回答
            #The type of the activities is voteup answer
            question_content = zhihu_client.get_voteup_answer_content(activity)

            try:
                #判断是否在数据库中已经存在
                #To check whether the activities is already store in the database
                check_query = "SELECT * FROM wheelbrother_voteupanswer WHERE answer_id=%s"
                self.cursor.execute(check_query, [question_content['answer_id']])
                check_model = self.cursor.fetchall()
                if len(check_model) > 0:
                    self.logger.info('赞同的答案已经在数据库中')
                    return
            except:
                self.logger.exception('store wheelbrother_voteupanswer error')

            voteup_answer_query = ("INSERT INTO wheelbrother_voteupanswer"+
                                   "(user_link,"+
                                   "username,"+
                                   "answer_id,"+
                                   "answer_content,"+
                                   "question_id,"+
                                   "answer_vote_count,"+
                                   "answer_comment_id,"+
                                   "answer_data_time)"+
                                   " VALUES(%s,%s,%s,%s,%s,%s,%s,%s)")

            self.cursor.execute(
                voteup_answer_query,
                [
                    question_content['user_link'],
                    ''.join(question_content['username']).encode('utf-8').strip(),
                    question_content['answer_id'],
                    ''.join(question_content['answer_content']).encode('utf-8').strip(),
                    question_content['question_id'],
                    question_content['answer_vote_count'],
                    question_content['answer_comment_id'],
                    question_content['answer_data_time'],
                ]
            )

            self.connection.commit()

            self.logger.info('\n赞同了回答 \n')
            self.logger.info('save voteup answer successful '+
                             question_content['answer_content']+'\n'+
                             'time : '+str(question_content['answer_data_time']))

            comments_json_result = zhihu_client.get_comment(question_content['answer_comment_id'])

            if comments_json_result is None:
                return

            for comment in comments_json_result['data']:
                if self.parse_comment_result(comment) is None:
                    break

            self.logger.info('waiting for 20s......')
            time.sleep(20)

        if activity.attrs['data-type-detail'] == 'member_follow_question':
            #关注了问题
            #The type of the activities is follow a question
            follow_question_content = zhihu_client.get_follow_question(activity)

            query_value = [
                follow_question_content['question_id'],
                follow_question_content['question_link'],
                ''.join(follow_question_content['question_title']).encode('utf-8').strip()
            ]


            follow_question_query = (
                "INSERT INTO wheelbrother_followquestion"+
                "(question_id,"+
                "question_link,"+
                "question_title)"
                " VALUES(%s,%s,%s)"
            )

            self.cursor.execute(
                follow_question_query,
                query_value
            )

            self.connection.commit()

            self.logger.info('\n 关注了问题 \n')
            self.logger.info('save follow question '+
                             follow_question_content['question_title'])

        if activity.attrs['data-type-detail'] == 'member_answer_question':
            #回答了问题
            #The type of the activities is answer a question
            answer_question_content = zhihu_client.get_member_answer_question(activity)
            try:
                #判断是否在数据库中已经存在
                #To check whether the activities is already store in the database
                check_query = "SELECT * FROM wheelbrother_answerquestion WHERE answer_id=%s"
                self.cursor.execute(check_query, [answer_question_content['answer_id']])
                check_model = self.cursor.fetchall()
                if len(check_model) > 0:
                    self.logger.info('回答的问题已经在数据库中\n')
                    return
            except:
                self.logger.exception('store wheelbrother_answerquestion error')

            answer_question_query = (
                "INSERT INTO wheelbrother_answerquestion"+
                "(question_id,"+
                "question_title,"+
                "answer_content,"+
                "answer_id,"+
                "created_time,"+
                "answer_comment_id)"
                " VALUES(%s,%s,%s,%s,%s,%s)"
            )

            query_value = [
                answer_question_content['question_id'],
                ''.join(answer_question_content['question_title']).encode('utf-8').strip(),
                ''.join(answer_question_content['answer_content']).encode('utf-8').strip(),
                answer_question_content['answer_id'],
                answer_question_content['created_time'],
                answer_question_content['answer_comment_id']
            ]

            self.cursor.execute(
                answer_question_query,
                query_value
            )

            self.connection.commit()

            self.logger.info('\n回答了问题 \n')
            self.logger.info('save answer question '+
                             answer_question_content['question_title']+' \n'+
                             'time : '+str(answer_question_content['created_time']))

            comments_json_result = zhihu_client.get_comment(
                answer_question_content['answer_comment_id']
            )

            if comments_json_result is None:
                return

            for comment in comments_json_result['data']:
                if self.parse_comment_result(comment) is None:
                    break

        if activity.attrs['data-type-detail'] == 'member_follow_column':
            #关注了专栏
            #The type of the activities is follow a column
            zhihu_client.logger.info('\n关注了专栏 \n')

        if activity.attrs['data-type-detail'] == 'member_voteup_article':
            #赞同了文章
            #The type of the activities is voteup a article
            voteup_article_content = zhihu_client.get_member_voteup_article(activity)

            try:
                #判断是否在数据库中已经存在
                #To check whether the activities is already store in the database
                check_query = "SELECT * FROM wheelbrother_voteuparticle WHERE article_url_token=%s"
                self.cursor.execute(check_query, [voteup_article_content['article_url_token']])
                check_model = self.cursor.fetchall()
                if len(check_model) > 0:
                    self.logger.info('赞同的文章已经在数据库中 \n')
                    return
            except:
                self.logger.exception('store wheelbrother_voteuparticle error')


            voteup_article_query = (
                "INSERT INTO wheelbrother_voteuparticle"+
                "(user_link,"+
                "article_title,"+
                "article_url_token,"+
                "article_id,"+
                "article_content,"+
                "created_time)"
                " VALUES(%s,%s,%s,%s,%s,%s)"
            )

            query_value = [
                voteup_article_content['user_link'],
                ''.join(voteup_article_content['article_title']).encode('utf-8').strip(),
                voteup_article_content['article_url_token'],
                voteup_article_content['article_id'],
                ''.join(voteup_article_content['article_content']).encode('utf-8').strip(),
                voteup_article_content['created_time'],
            ]

            self.cursor.execute(
                voteup_article_query,
                [
                    voteup_article_content['user_link'],
                    ''.join(voteup_article_content['article_title']).encode('utf-8').strip(),
                    voteup_article_content['article_url_token'],
                    voteup_article_content['article_id'],
                    ''.join(voteup_article_content['article_content']).encode('utf-8').strip(),
                    voteup_article_content['created_time'],
                ]
            )

            self.connection.commit()

            self.logger.info('\n赞同了文章 \n')
            self.logger.info('save voteup article '+
                             voteup_article_content['article_title']+' \n'+
                             'time : '+str(voteup_article_content['created_time']))

        if activity.attrs['data-type-detail'] == 'member_create_article':
            #发布了文章
            #The type of the activities is created a article
            self.logger.info('\n发布了文章 \n')


    def parse_comment_result(self, comment):
        '''
            解析赞同回答的评论
            Tp Parse the comment of the voteup answer
        '''

        try:
            #判断是否在数据库中已经存在
            #To check whether the activities is already store in the database
            check_query = "SELECT * FROM wheelbrother_voteupcomment WHERE comment_id=%s"
            self.cursor.execute(check_query, [comment['id']])
            check_model = self.cursor.fetchall()
            if len(check_model) > 0:
                self.logger.info('评论已经在数据库中')
                return
        except:
            self.logger.exception('store wheelbrother_voteupcomment error')
            return

        try:
            #有匿名的情况
            #when the comment is post by a anonymous user
            user_link = comment['author']['url']
            username = comment['author']['name']
        except:
            user_link = Zhihu.ZHIHU_URL
            username = 'anonymous'

        voteup_comment_query = ("INSERT INTO wheelbrother_voteupcomment"+
                                "(comment_id,"+
                                "comment_content,"+
                                "created_time,"+
                                "like_count,"+
                                "dislikes_count,"+
                                "in_reply_to_comment_id,"+
                                "user_link,"+
                                "username)"
                                " VALUES(%s,%s,%s,%s,%s,%s,%s,%s)")
        query_value = [
            comment['id'],
            ''.join(comment['content']).encode('utf-8').strip(),
            comment['createdTime'],
            comment['likesCount'],
            comment['dislikesCount'],
            comment['inReplyToCommentId'],
            user_link,
            ''.join(username).encode('utf-8').strip(),
        ]
        self.cursor.execute(
            voteup_comment_query,
            query_value
        )

        self.connection.commit()

        self.logger.info('save voteup comment '+
                         ''.join(comment['content']).encode('utf-8').strip()+'/n'+
                         'time : '+str(comment['createdTime']))
        return query_value

    def crawl_collection(self, zhihu_client):
        '''
            爬取收藏夹内容
            Clawl the content all the collection
        '''

        activities_result_set = list()
        crawl_times = 0
        pages = 1
        while True:
            try:
                response = zhihu_client.get_collection_activites(61913303, pages)
                pages = pages + 1
                soup = BeautifulSoup(response, 'html.parser')
                activities_result_set = zhihu_client.parse_collection_activites_content(soup)
            except requests.exceptions.ConnectionError:
                self.logger.exception('connection refused')
                print 'Catch collection activities connection refused, waiting for 120s......'
                time.sleep(120)
                continue
            except ValueError:
                self.logger.exception('Catch activities ValueError'+
                                      ' maybe No JSON object could be decoded')
                print 'Get collection activities error, waiting for 1200s, and then break......'
                time.sleep(1200)
                break
            except:
                self.logger.exception('Catch activities error')
                print 'Get collection activities error, waiting for 1200s, and then break......'
                time.sleep(1200)
                break


            for collection_activity in activities_result_set:
                is_store_in_database = False
                try:
                    #判断是否在数据库中已经存在
                    #To check whether the activities is already store in the database
                    check_query = "SELECT * FROM wheelbrother_collectionanswer WHERE answer_id=%s"
                    self.cursor.execute(check_query, [collection_activity['answer_id']])
                    check_model = self.cursor.fetchall()
                    if len(check_model) > 0:
                        self.logger.info('收藏夹的问题已经在数据库中\n')
                        is_store_in_database = True
                    else:
                        is_store_in_database = False
                except:
                    self.logger.exception('store wheelbrother_collectionanswer error')


                if is_store_in_database:
                    continue

                collection_answer_query = (
                    "INSERT INTO wheelbrother_collectionanswer"+
                    "(question_link,"+
                    "answer_id,"+
                    "answer_title,"+
                    "answer_content,"+
                    "author_name,"+
                    "author_link,"+
                    "answer_comment_id)"
                    " VALUES(%s,%s,%s,%s,%s,%s,%s)"
                )

                collection_answer_value = [
                    collection_activity['question_link'],
                    collection_activity['answer_id'],
                    ''.join(collection_activity['answer_title']).encode('utf-8').strip(),
                    ''.join(collection_activity['answer_content']).encode('utf-8').strip(),
                    ''.join(collection_activity['author_name']).encode('utf-8').strip(),
                    collection_activity['author_link'],
                    collection_activity['answer_comment_id'],
                ]


                self.cursor.execute(
                    collection_answer_query,
                    collection_answer_value
                )

                self.connection.commit()

                self.logger.info('\n 爬取了一个回答 \n')
                self.logger.info('save collection answer '+
                                 collection_activity['answer_title']+' \n'+
                                 'answer_id : '+str(collection_activity['answer_id']))

            # crawl_times = crawl_times + 1
            # if crawl_times == 10:
            #     self.logger.info('crawl collection activities 10 times, sleep 60s...')
            #     time.sleep(60)
            # elif crawl_times == 20:
            #     self.logger.info('crawl collection activities 20 times, sleep 80s...')
            #     time.sleep(80)
            # elif crawl_times == 30:
            #     self.logger.info('crawl collection activities 30 times, sleep 1200s...')
            #     crawl_times = 0
            #     time.sleep(1200)
            # else:
            #     self.logger.info('crawl collection activities, waiting for 20s...')
            #     time.sleep(20)


    def crawl_followees(self, zhihu_client):
        '''
            爬取关注列表
            To get the user's follwees list
        '''

        followees_result_set = list()
        crawl_times = 0
        off_set = 200
        while True:
            try:
                response = zhihu_client.get_followees_list('excited-vczh', off_set)
                json_response = json.loads(response)
            except requests.exceptions.ConnectionError:
                self.logger.exception('connection refused')
                print 'Catch  followees connection refused, waiting for 120s......'
                time.sleep(120)
                continue
            except ValueError:
                self.logger.exception('Catch followees ValueError'+
                                      ' maybe No JSON object could be decoded')
                print 'Get  followees error, waiting for 1200s, and then break......'
                time.sleep(1200)
                break
            except:
                self.logger.exception('Catch followees error')
                print 'Get  followees error, waiting for 1200s, and then break......'
                time.sleep(1200)
                break

            off_set = off_set + 20
            followees_result_set = json_response['data']

            for followees in followees_result_set:
                if not followees['is_following']:
                    time.sleep(20)
                    follow_response = zhihu_client.follow_member(followees['url_token'])
                    json_follow_response = json.loads(follow_response)
                    if json_follow_response.has_key['error']:
                        self.logger.info('crawl too many times and too fast,'+
                                         ' have a rest, sleep 1200s...')
                        time.sleep(1200)
                        zhihu_client.follow_member(followees['url_token'])

                    self.logger.info('关注用户 : '+''.join(followees['name']).encode('utf-8'))
                else:
                    self.logger.info('name '+''.join(followees['name']).encode('utf-8')+' 已关注')

            # crawl_times = crawl_times + 1
            # if crawl_times == 10:
            #     self.logger.info('crawl followees 10 times, sleep 60s...')
            #     time.sleep(60)
            # elif crawl_times == 20:
            #     self.logger.info('crawl followees 20 times, sleep 80s...')
            #     time.sleep(80)
            # elif crawl_times == 30:
            #     self.logger.info('crawl followees 30 times, sleep 1200s...')
            #     crawl_times = 0
            #     time.sleep(1200)
            # else:
            #     self.logger.info('crawl followees activities, waiting for 20s...')
            #     time.sleep(20)


    def crawl_my_feed(self, zhihu_client):
        '''
            爬取主页动态
            To get user's own feed of the main page
        '''
        crawl_times = 0
        start = 0
        offset = 10
        while True:
            try:
                response = zhihu_client.get_my_activities(start, offset)
                json_response = json.loads(response)
            except requests.exceptions.ConnectionError:
                self.logger.exception('connection refused')
                print 'Catch  feed connection refused, waiting for 120s......'
                time.sleep(120)
                continue
            except ValueError:
                self.logger.exception('Catch feed ValueError'+
                                      ' maybe No JSON object could be decoded')
                print 'Get  feed error, waiting for 1200s, and then break......'
                time.sleep(1200)
                break
            except:
                self.logger.exception('Catch feed error')
                print 'Get  feed error, waiting for 1200s, and then break......'
                time.sleep(1200)
                break

            feeds = json_response['msg']
            start = start + offset
            crawl_times = crawl_times + 1
            self.logger.info('feed num : '+str(start))
            for item in feeds:
                self.parse_feed_activiteis(zhihu_client, item)


            if start >= 1000:
                #当爬取1000条数据后，从新开始爬
                #When get more than 1000 data, then start over
                break

            # if crawl_times == 10:
            #     self.logger.info('crawl feed 10 times, sleep 60s...')
            #     time.sleep(60)
            # elif crawl_times == 20:
            #     self.logger.info('crawl feed 20 times, sleep 80s...')
            #     time.sleep(80)
            # elif crawl_times == 30:
            #     self.logger.info('crawl feed 30 times, sleep 1200s...')
            #     crawl_times = 0
            #     time.sleep(1200)
            # else:
            #     self.logger.info('crawl feed activities, waiting for 20s...')
            #     time.sleep(20)

    def parse_feed_activiteis(self, zhihu_client, activiteis):
        '''根据不同的标签来判断feed动态的类型'''
        soup = BeautifulSoup(activiteis, 'html.parser')
        data_meta = {}
        try:
            data_meta = json.loads(soup.find(
                'meta',
                itemprop='ZReactor'
            ).get('data-meta'))
        except AttributeError:
            if self.logger:
                self.logger.exception(AttributeError.message)
            return

        if data_meta['source_type'] == 'member_voteup_answer':

            user_link = soup.find('a', class_='author-link').get('href')
            username = soup.find('a', class_='author-link').string
            answer_content = soup.find('textarea', class_='content').string

            question_link = soup.find('a', class_='question_link').get('href')
            pattern = r'(?<=question/).*?(?=/answer)'
            question_id = re.findall(pattern, question_link)[0]

            question_title = soup.find('h2', class_='feed-title').find('a').string
            answer_id = soup.find('meta', itemprop='answer-url-token').get('content')
            answer_data_time = soup.find('span', class_='time').get('data-timestamp')
            answer_vote_count = data_meta['voteups']
            answer_comment_id = soup.find('meta', itemprop='ZReactor').get('data-id')

            try:
                #判断是否在数据库中已经存在
                check_query = "SELECT * FROM wheelbrother_feed_voteupanswer WHERE answer_id=%s"
                self.cursor.execute(check_query, [answer_id])
                check_model = self.cursor.fetchall()
                if len(check_model) > 0:
                    self.logger.info('feed中赞同的答案 '+str(
                        ''.join(question_title).encode('utf-8').strip())+' 已经在数据库中')
                    return
            except Exception:
                self.logger.exception(Exception.message)


            feed_voteup_answer_query = (
                "INSERT INTO wheelbrother_feed_voteupanswer"+
                "(user_link,"+
                "username,"+
                "answer_content,"+
                "question_id,"+
                "question_title,"+
                "answer_id,"+
                "answer_data_time,"+
                "answer_vote_count,"+
                "answer_comment_id)"+
                " VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)"
            )

            self.cursor.execute(
                feed_voteup_answer_query,
                [
                    user_link,
                    ''.join(username).encode('utf-8').strip(),
                    ''.join(answer_content).encode('utf-8').strip(),
                    question_id,
                    ''.join(question_title).encode('utf-8').strip(),
                    answer_id,
                    answer_data_time,
                    answer_vote_count,
                    answer_comment_id
                ]
            )

            self.connection.commit()
            self.logger.info('save feed member voteup answer '+str(
                ''.join(question_title).encode('utf-8').strip()))

        if data_meta['source_type'] == 'member_follow_question':

            question_link = soup.find('a', class_='question_link').get('href')
            question_id = soup.find('meta', itemprop='question-url-token').get('content')
            question_title = soup.find('h2', class_='feed-title').find('a').string

            try:
                #判断是否在数据库中已经存在
                check_query = "SELECT * FROM wheelbrother_feed_followquestion WHERE question_id=%s"
                self.cursor.execute(check_query, [question_id])
                check_model = self.cursor.fetchall()
                if len(check_model) > 0:
                    self.logger.info('feed中关注的问题 '+str(
                        ''.join(question_title).encode('utf-8').strip())+' 已经在数据库中')
                    return
            except Exception:
                self.logger.exception(Exception.message)

            query_value = [
                question_id,
                question_link,
                ''.join(question_title).encode('utf-8').strip()
            ]


            member_follow_question_query = (
                "INSERT INTO wheelbrother_feed_followquestion"+
                "(question_id,"+
                "question_link,"+
                "question_title)"
                " VALUES(%s,%s,%s)"
            )

            self.cursor.execute(
                member_follow_question_query,
                query_value
            )

            self.connection.commit()
            self.logger.info('save feed follow question '+str(
                ''.join(question_title).encode('utf-8').strip()))

        if data_meta['source_type'] == 'member_answer_question':

            question_link = soup.find('a', class_='question_link').get('href')
            pattern = r'(?<=question/).*?(?=/answer)'
            question_id = re.findall(pattern, question_link)[0]

            question_title = soup.find('h2', class_='feed-title').find('a').string
            answer_content = soup.find('textarea', class_='content').string
            answer_id = soup.find('meta', itemprop='answer-url-token').get('content')
            created_time = soup.find('span', class_='time').get('data-timestamp')
            answer_comment_id = soup.find('meta', itemprop='ZReactor').get('data-id')

            try:
                #判断是否在数据库中已经存在
                check_query = "SELECT * FROM wheelbrother_feed_answerquestion WHERE answer_id=%s"
                self.cursor.execute(check_query, [answer_id])
                check_model = self.cursor.fetchall()
                if len(check_model) > 0:
                    self.logger.info('feed中回答的问题 '+str(
                        ''.join(question_title).encode('utf-8').strip())+' 已经在数据库中')
                    return
            except Exception:
                self.logger.exception(Exception.message)

            query_value = [
                question_id,
                ''.join(question_title).encode('utf-8').strip(),
                ''.join(answer_content).encode('utf-8').strip(),
                answer_id,
                created_time,
                answer_comment_id
            ]


            member_answer_question_query = (
                "INSERT INTO wheelbrother_feed_answerquestion"+
                "(question_id,"+
                "question_title,"+
                "answer_content,"+
                "answer_id,"+
                "created_time,"+
                "answer_comment_id)"
                " VALUES(%s,%s,%s,%s,%s,%s)"
            )

            self.cursor.execute(
                member_answer_question_query,
                query_value
            )

            self.connection.commit()
            self.logger.info('save feed member answer question '+str(
                ''.join(question_title).encode('utf-8').strip()))

        if data_meta['source_type'] == 'member_follow_column':
            pass
        if data_meta['source_type'] == 'member_voteup_article':
            pass
        if data_meta['source_type'] == 'member_create_article':
            pass

    def voteup_activities(self, zhihu_client, answer_id):
        response = zhihu_client.vote_up_answer(answer_id)
        print response

if __name__ == "__main__":
    my_zhihu_crawler = zhihu_crawler()
    while True:
        my_zhihu_crawler.main()
        # time.sleep(1800)
