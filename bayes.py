#coding=utf-8
import MySQLdb
import jieba
import json
from collections import Counter
import numpy
import re
import sys

reload(sys)
sys.setdefaultencoding('utf-8')

class naive_bayesian(object):

    def __init__(self):
        self.connection = MySQLdb.connect(
            host='42.96.208.219',
            port=3306,
            user='root',
            passwd='root',
            db='mysite',
            charset="utf8"
        )
        self.cursor = self.connection.cursor(cursorclass=MySQLdb.cursors.DictCursor)

    def is_chinese(self, string):
        """determine whether the word is Chinese"""
        zh_pattern = re.compile(u'[\u4e00-\u9fa5]+')
        match = zh_pattern.search(string)

        if match:
            return True
        else:
            return False


    def get_high_frequency_word(self):
        '''
            Get the highest frequency of the word from the database
        '''
        activites = {}
        activitiy_query = "SELECT * FROM wheelbrother_voteupanswer ORDER BY id DESC"
        self.cursor.execute(activitiy_query)
        activites = self.cursor.fetchall()

        activitiy_query = "SELECT * FROM wheelbrother_collectionanswer ORDER BY id DESC"
        self.cursor.execute(activitiy_query)
        voteup_activites = self.cursor.fetchall()
        print type(voteup_activites)
        activites = activites + voteup_activites
        # target_index = 100
        word_list = list()
        chinese_word_string = list()
        activity_string = list()
        for activity in activites:
            activity_string.append(activity['answer_content'])

        for item in ''.join(activity_string):
            if self.is_chinese(item):
                chinese_word_string.append(item)

        seg_list = jieba.cut(''.join(chinese_word_string))

        for item in seg_list:
            if len(item) >= 2:
                word_list.append(item)

        word_count = Counter(word_list)
        json_dict = dict()
        for item in word_count.most_common(2000):
            json_dict[item[0]] = item[1]

        with open("key_word.json", "w") as outfile:
            json.dump(json_dict, outfile, ensure_ascii=False, indent=4)


    def set_of_word_to_vector(self, vocab_list, input_set):
        '''
            Create a vector which all the element are 0,
            and change the element to one which contain high frequency word
        '''
        return_vector = [0]*len(input_set)
        for word in input_set:
            if word in vocab_list:
                return_vector[input_set.index(word)] = 1
            else:
                print "the word : %s is not in my vocabulary ! " % word

        return return_vector

    def train_naive_bayes(self, train_matrix, key_word_list):
        '''
            Training Naive Bayesian Classifier
        '''
        num_train_docs = len(train_matrix)
        num_words = len(train_matrix[0])
        posibility_of_target = numpy.sum(key_word_list)/numpy.float(num_train_docs)
        #Init possibility
        posibility_zero_num = numpy.ones(num_words)
        posibility_one_num = numpy.ones(num_words)
        posibility_zero_denom = 2.0
        posibility_one_denom = 2.0

        for i in range(num_train_docs):
            if key_word_list[i] == 1:
                posibility_one_num += train_matrix[i]
                posibility_one_denom += numpy.sum(train_matrix[i])
            else:
                posibility_zero_num += train_matrix[i]
                posibility_zero_denom += numpy.sum(train_matrix[i])
        posibility_one_vector = posibility_one_num/posibility_one_denom
        posibility_zero_vector = posibility_zero_num/posibility_one_denom
        return posibility_zero_vector, posibility_one_vector, posibility_of_target

