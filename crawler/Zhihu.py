#coding=utf-8
""" zhihu website crawler API """
import re
import time
import random
import json
import os
import requests
import cookielib
from PIL import Image


ZHIHU_URL = 'https://www.zhihu.com'
VCZH_URL = ZHIHU_URL + '/people/excited-vczh'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 '+
                  '(Linux; Android 6.0; Nexus 5 Build/MRA58N)'+
                  ' AppleWebKit/537.36 (KHTML, like Gecko)'+
                  ' Chrome/57.0.2950.4 Mobile Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Host': "www.zhihu.com",
    'Origin': "https://www.zhihu.com",
    'Pragma': "no-cache",
    'Referer': "https://www.zhihu.com/",
    'X-Requested-With': "XMLHttpRequest"
}


class ZhihuClient(object):
    '''
        知乎爬虫接口
        The Crawler initial method
    '''

    def __init__(self, logger=None):
        # 使用登录cookie信息
        self.session = requests.session()
        self.session.cookies = cookielib.LWPCookieJar(filename='cookies')
        try:
            self.session.cookies.load(ignore_discard=True)
        except:
            print "Cookie 未能加载"

        if logger:
            self.logger = logger

        #知乎改版后，POST请求需要加X-Xsrftoken，不然会出现403
        self.xsrf_token = self.get_xsrf()

        self.ip_proxy_list = self.get_proxy()

    def login(self, account, password):
        """
            登录知乎
            Logging Zhihu
        """
        post_url = 'https://www.zhihu.com/login/phone_num'

        post_data = {
            '_xsrf':self.xsrf_token,
            'password':password,
            'remember_me': 'true',
            'phone_num': account,
        }

        # 需要输入验证码后才能登录成功
        # Need the verification code to loggin
        post_data["captcha"] = self.get_captcha()
        login_page = self.session.post(post_url, data=post_data, headers=HEADERS)
        login_code = login_page.text
        print login_page.status_code
        print login_code

        self.session.cookies.save()

    def is_login(self):
        '''
            通过查看用户个人信息来判断是否已经登录
            By visiting the profile page to check the logging state
        '''
        url = "https://www.zhihu.com/settings/profile"
        login_response = self.session.get(
            url,
            headers=HEADERS,
            allow_redirects=False,
            verify=False
        )

        login_code = login_response.status_code

        # print 'login_response : '+login_response.text

        if login_code == 200:
            print 'Logging \n'
            return True
        else:
            print 'Not Logging yet \n'
            return False


    def get_captcha(self):
        '''
            获取验证码
            Get the verification code
        '''
        t = str(int(time.time() * 1000))
        captcha_url = 'https://www.zhihu.com/captcha.gif?r=' + t + "&type=login"
        r = self.session.get(captcha_url, headers=HEADERS)
        with open('captcha.jpg', 'wb') as f:
            f.write(r.content)
            f.close()
        # 用pillow 的 Image 显示验证码
        # 如果没有安装 pillow 到源代码所在的目录去找到验证码然后手动输入
        # Use pillow to show the Image, and if there is no pillow check the image by manual
        try:
            im = Image.open('captcha.jpg')
            im.show()
            im.close()
        except:
            print '请到 %s 目录找到captcha.jpg 手动输入' % os.path.abspath('captcha.jpg')
        captcha = input("please input the captcha\n>")
        return captcha


    def get_xsrf(self):
        '''_xsrf 是一个动态变化的参数'''
        index_url = 'https://www.zhihu.com'
        # 获取登录时需要用到的_xsrf
        # when logging it need a token, and the token is needed when do the all activities
        index_page = self.session.get(index_url, headers=HEADERS, verify=False)
        html = index_page.text
        pattern = r'name="_xsrf" value="(.*?)"'
        # 这里的_xsrf 返回的是一个list
        # the _xsrf is a list
        _xsrf = re.findall(pattern, html)
        return _xsrf[0]

    def get_proxy(self):
        ip_dict_json = dict()
        with open('ip_proxy.json', 'r') as json_file:
            ip_dict_json = json.load(json_file)
        return ip_dict_json['ip_proxy']

    def get_random_proxy(self):
        ip_dict = random.choice(self.ip_proxy_list)
        ip_proxy = 'http:\\'+str(ip_dict['ip'])+':'+str(ip_dict['port'])
        return ip_proxy

    def get_more_activities(self, limit, start):
        '''
            获取更多的用户动态
        '''
        api_url = VCZH_URL + '/activities'
        query_data = {
            'limit':limit,
            'start':start,
        }

        HEADERS['X-Xsrftoken'] = self.xsrf_token

        response = self.session.post(
            api_url,
            params=query_data,
            headers=HEADERS,
            verify=False,
            proxies=self.get_random_proxy()
        )

        return response.text

    def get_voteup_answer_content(self, activity):
        '''
            解析赞同回答的内容
        '''
        #回答者的用户信息
        #Informaton of user who answer the question
        author_link_top = activity.find_all('span', class_='summary-wrapper')
        try:
            author_link = author_link_top[0].find('a', class_='author-link')
            user_link = author_link.get('href')
            username = author_link.get_text()
        except:
            '''
                可能会造成的异常为Nonetype, 和IndexError，还不知道为什么会出现有的答案的html结构会不一样

                May cause the Nonetype error and IndexError, still don't kwow why
                sometime the structrue of the html is different
            '''
            user_link = ZHIHU_URL
            username = 'anonymous'

        #答案的信息
        #Information of Answer
        answer_div = activity.find_all('div', class_='zm-item-answer ')
        answer_id = answer_div[0].get('data-atoken')
        answer_data_time = answer_div[0].get('data-created')
        answer_comment_id = answer_div[0].get('data-aid')
        answer_content = answer_div[0].find('textarea', class_='content').string
        answer_vote_count = answer_div[0].find('a', class_='meta-item'+
                                               ' votenum-mobile zm-item-vote-count'+
                                               ' js-openVoteDialog').find('span').string

        #问题的信息
        #Information of Question
        question_link_a = activity.find_all('a', class_='question_link')
        question_link = question_link_a[0]['href']
        pattern = r'(?<=question/).*?(?=/answer)'
        question_id = re.findall(pattern, question_link)[0]

        question_content = {
            'user_link':user_link,
            'username':username,
            'answer_id':answer_id,
            'answer_content':answer_content,
            'question_id':question_id,
            'answer_vote_count':answer_vote_count,
            'answer_comment_id':answer_comment_id,
            'answer_data_time':answer_data_time
        }

        return question_content

    def get_comment(self, answer_comment_id):
        '''
            获取赞同回答的评论
            Get the activities comment
        '''
        current_page = 1
        #获取评论url
        #get comment url
        MORE_COMMENT_URL = ZHIHU_URL + '/r/answers/'+answer_comment_id+'/comments?page='

        try:
            #只获取一页的评论,同时赞数最多的评论就在第一页
            #only need to get the first page's commments,
            #because the popular comment at the first page
            comments = self.session.get(
                MORE_COMMENT_URL+str(current_page),
                headers=HEADERS,
                verify=False,
                proxies=self.get_random_proxy()
                )
        except requests.exceptions.ConnectionError:
            if self.logger:
                self.logger.exception('Get comment connection refused')
            time.sleep(40)
            return
        except:
            if self.logger:
                self.logger.exception('Get comment error')
            time.sleep(40)
            return

        try:
            comments_json_result = json.loads(comments.text)
            if len(comments_json_result['data']) < 1:
                return

            return comments_json_result
        except ValueError:
            if self.logger:
                self.logger.exception('Myabe No JSON object could be decoded')
            return



    def get_follow_question(self, activity):
        '''
            解析关注问题的信息
            Parse the activities which user followed
        '''
        question_link = activity.find('a', class_='question_link').get('href')
        question_id = re.findall(r"(?<=/question/).*", question_link)[0]
        question_title = activity.find('a', class_='question_link').string

        follow_question_content = {
            'question_link':question_link,
            'question_id':question_id,
            'question_title':question_title,
        }

        return follow_question_content

    def get_member_answer_question(self, activity):
        '''
            解析回答问题的信息
            Parse the activities which user answered
        '''
        question_link = activity.find('a', class_='question_link').get('href')
        question_id = re.findall(r'(?<=question/).*?(?=/answer)', question_link)[0]
        question_title = activity.find('a', class_='question_link').string
        answer_content = activity.find('textarea', class_='content').string
        answer_id = activity.find('div', class_='zm-item-answer ').get('data-atoken')
        answer_comment_id = activity.find('div', class_='zm-item-answer ').get('data-aid')
        created_time = activity.find('div', class_='zm-item-answer ').get('data-created')

        answer_question_content = {
            'question_id':question_id,
            'question_title':question_title,
            'answer_content':answer_content,
            'answer_id':answer_id,
            'created_time':created_time,
            'answer_comment_id':answer_comment_id
        }

        return answer_question_content

    def get_member_voteup_article(self, activity):
        '''
            解析赞同文章的信息
            Parse the activities which user voteup
        '''
        try:
            user_link = activity.find(
                'div',
                class_='author-info summary-wrapper'
                ).find('a').get('href')
        except:
            user_link = ''

        article_title = activity.find('a', class_='post-link').string

        article_info_div = activity.find('div', class_='zm-item-feed zm-item-post')
        article_info_div_meta = article_info_div.find_all('meta')

        article_url_token = article_info_div_meta[0].get('content')
        article_id = article_info_div_meta[1].get('content')
        article_content = activity.find('textarea', class_='content').string
        created_time = activity.get('data-time')

        voteup_article_content = {
            'user_link':ZHIHU_URL+user_link,
            'article_title':article_title,
            'article_url_token':article_url_token,
            'article_id':article_id,
            'article_content':article_content,
            'created_time':created_time
        }

        return voteup_article_content

    def get_collection_activites(self, collection_id, page_num):
        '''
            获取收藏夹的内容
            Crawl the collection activities
        '''
        collection_url = ZHIHU_URL + '/collection/'+str(collection_id)+'/?page='+str(page_num)
        response = self.session.get(
            collection_url,
            headers=HEADERS,
            verify=False,
            proxies=self.get_random_proxy()
        )

        return response.text

    def parse_collection_activites_content(self, content):
        '''
            解析收藏夹的内容
            Parse the collection activities
        '''
        activities_result_set = list()
        activites = content.find_all('div', class_='zm-item')
        for activity in activites:
            activity_result_set = {}
            answer_title = activity.find('h2', class_='zm-item-title').find('a').string
            question_link = activity.find('h2', class_='zm-item-title').find('a').get('href')
            try:
                author_name = activity.find('a', class_='author-link').string
                author_link = activity.find('a', class_='author-link').get('href')
            except AttributeError:
                author_name = 'anonymity'
                author_link = ZHIHU_URL

            answer_content = activity.find('textarea', class_='content').string
            try:
                answer_comment_id = activity.find('div', class_='zm-item-answer').get('data-aid')
                answer_id = activity.find('div', class_='zm-item-answer').get('data-atoken')
            except AttributeError:
                answer_comment_id = '0'
                answer_id = '0'

            activity_result_set['answer_title'] = answer_title
            activity_result_set['question_link'] = question_link
            activity_result_set['author_name'] = author_name
            activity_result_set['author_link'] = author_link
            activity_result_set['answer_content'] = answer_content
            activity_result_set['answer_comment_id'] = answer_comment_id
            activity_result_set['answer_id'] = answer_id
            activities_result_set.append(activity_result_set)

        return activities_result_set

    def get_followees_list(self, username, off_set):
        '''
            获取用户关注列表
        '''
        get_data = {
            'include':('data[*].answer_count,'+
                       'articles_count,'+
                       'gender,'+
                       'follower_count,'+
                       'is_followed,'+
                       'is_following,'+
                       'badge[?(type=best_answerer)].topics'),
            'offset':off_set,
            'limit':20
        }

        #主要是使用桌面的User-Agent来获取关注人会方便很多
        #Because of the Zhihu API, Use PC User-Agent could be more convinience
        HEADERS['User-Agent'] = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_3)'+
                                 ' AppleWebKit/537.36 (KHTML, like Gecko)'+
                                 ' Chrome/56.0.2924.87 Safari/537.36')

        url = 'https://www.zhihu.com/api/v4/members/'+str(username)+'/followees'

        response = self.session.get(
            url,
            headers=HEADERS,
            params=get_data,
            proxies=self.get_random_proxy()
        )

        return response.text


    def follow_member(self, username):
        '''
            follow user
        '''
        #主要是使用桌面的User-Agent来获取关注人会方便很多
        #Because of the Zhihu API, Use PC User-Agent could be more convinience
        HEADERS['User-Agent'] = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_3)'+
                                 ' AppleWebKit/537.36 (KHTML, like Gecko)'+
                                 ' Chrome/56.0.2924.87 Safari/537.36')

        follow_url = 'https://www.zhihu.com/api/v4/members/'+str(username)+'/followers'
        response = self.session.post(
            follow_url,
            headers=HEADERS,
            verify=False,
            proxies=self.get_random_proxy()
        )

        print response.text
        return response.text

    def get_my_activities(self, start, offset):
        '''
            get my own main page's feed

            start: from which feed's num start to crawl

            offset: the number of the feed that you want to get at one time
        '''

        feed_url = 'https://www.zhihu.com/node/TopStory2FeedList'

        post_data = ('params=%7B%22offset%22%3A{0}'+
                     '%2C%22start%22%3A%22{1}%22'+
                     '%7D&method=next').format(offset, start)


        headers = {
            'Accept':'*/*',
            'Accept-Encoding':'gzip, deflate, br',
            'Accept-Language':'en-US,en;q=0.8,zh-CN;q=0.6,zh;q=0.4,zh-TW;q=0.2,ja;q=0.2,ru;q=0.2',
            'Connection':'keep-alive',
            'Content-Length':'66',
            'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8',
            'Origin':'https://www.zhihu.com',
            'Referer':'https://www.zhihu.com/',
            'User-Agent': 'Mozilla/5.0 (Linux;'+
                          'Android 6.0; Nexus 5 Build/MRA58N) '+
                          'AppleWebKit/537.36 (KHTML, like Gecko)'+
                          'Chrome/56.0.2924.87 Mobile Safari/537.36',
            'X-Requested-With':'XMLHttpRequest',
            'X-Xsrftoken':self.xsrf_token
        }

        HEADERS['Xsrftoken'] = self.xsrf_token


        response = self.session.post(
            feed_url,
            data=post_data,
            headers=headers,
            proxies=self.get_random_proxy()
        )

        return response.text

    def vote_up_answer(self, answer_id):
        '''
            voteup activities
        '''
        request_url = 'https://www.zhihu.com/node/AnswerVoteInfoV2'
        HEADERS['Xsrftoken'] = self.xsrf_token

        get_data = {
            'params':{
                'answer_id':answer_id
            }
        }

        response = self.session.get(
            request_url,
            headers=HEADERS,
            params=get_data,
            proxies=self.get_random_proxy()
        )

        return response.text
