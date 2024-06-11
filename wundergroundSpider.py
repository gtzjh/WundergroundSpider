import requests
import pandas as pd
import numpy as np
from tqdm import tqdm
import time, json, os


def spider(req_url, sleep_time, start_date, end_date):
    headers = {
        "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36",
        "X-Requested-With":"XMLHttpRequest"
        }
    records_list = []
    date_list = pd.date_range(start_date, end_date, freq = 'D').strftime('%Y%m%d')

    for i in tqdm(date_list):
        url = req_url + '&startDate=' + i + '&endDate=' + i
        try:
            respon = requests.get(url, timeout = 30, headers = headers)
            if respon.status_code == 200:
                data = json.loads(respon.text)['observations']
                records_list = records_list + data
            else:
                with open('error.txt', 'a+') as f0:
                    f0.write(i + ',' + respon.status_code + ',' + '\n')
        except Exception as e:
            print(e)
            with open('error.txt', 'a+') as f1:
                f1.write(i + '\n')
        time.sleep(sleep_time)
    
    df = pd.DataFrame.from_records(records_list)
    df.to_csv('data.csv', encoding = 'utf-8', index = False)
    return None


# 读取error.txt文件的内容，对错误的参数重新爬取 
def supply(req_url, sleep_time):
    headers = {
        "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36",
        "X-Requested-With":"XMLHttpRequest"
        }
    records_list = []
    with open('error.txt', 'r') as f:
        lines = f.readlines()
        date_list = list(map(lambda x: x[0:8], lines))

    for i in tqdm(date_list):
        url = req_url + '&startDate=' + i + '&endDate=' + i
        try:
            respon = requests.get(url, timeout = 30, headers = headers)
            if respon.status_code == 200:
                data = json.loads(respon.text)['observations']
                records_list = records_list + data
            else:
                with open('error.txt', 'a+') as f0:
                    f0.write(i + ',' + respon.status_code + ',' + '\n')
        except Exception as e:
            print(e)
            with open('error.txt', 'a+') as f1:
                f1.write(i + '\n')
        time.sleep(sleep_time)
    
    df = pd.DataFrame.from_records(records_list)
    df.to_csv('append_data.csv', encoding = 'utf-8', index = False)
    return None


def concat(file0, file1):
    df0 = pd.read_csv(file0, encoding = 'utf-8')
    df1 = pd.read_csv(file1, encoding = 'utf-8')
    df2 = pd.concat([df0, df1])
    return df2


def cleanData(df0, reset_start_time_index, reset_end_time_index):
    '''
    day_ind: 白天还是晚上
    temp: 气温
    wx_icon: 不知道用来干什么，其日变化不明显，只有三种值
    icon_extd: wx_icon后面补两个0，也是不知道用来干什么
    wx_phrase: 文字描述天气状况，如晴朗（fair），cloudy（多云）， windy（有风）
    dewPt: 露点温度
    heat_index:
    pressure: 气压
    vis: 可视范围
    wc: 未知
    wdir: 风向 0-365度 【注意这个理应被当成一个类型变量！！！！】
    wdir_cardinal: 风基数 文字描述
    gust: 阵风，不知道用来干什么，而且只有4819条记录，扔掉
    wspd: 风速
    uv_desc: 紫外线强度 文字描述
    feels_like: 体感温度 （作用不大）
    uv_index: 紫外线指数 整数描述
    clds: 未知
    humidity: 相对湿度
    suntime: 日照时数，根据 uv index 来计算，uv index为0就是黑夜，正就是白天，其中1是阴雨天。
    '''

    assert isinstance(df0, pd.DataFrame)
    
    # 注意! 由于爬下来的时间是GMT时间，所以使用apply函数对 “valid_time_gmt” 这一列数据增加 8h ，即28800秒，这样得到的就是北京时间
    # 如果需要爬取其他时区的数据，需要额外调整
    df0['time'] = pd.to_datetime(df0['valid_time_gmt'].apply(lambda x: x + 28800), unit='s')
    
    # 去掉无用字段
    df1 = df0.drop(['key', 'class', 'obs_id', 'obs_name', 
                    'valid_time_gmt', 'expire_time_gmt', 'day_ind',
                    'feels_like', 'wx_icon', 'icon_extd', 'gust'],
                    axis = 1) \
             .set_index(['time']) \
             .sort_index() \
             # .dropna(how = 'all', axis = 1) # 有些列全为空值
    
    # 华氏度转摄氏度
    df1['temp'] = df1['temp'].apply(lambda x: (x-32)/1.8) # 气温
    df1['dewPt'] = df1['dewPt'].apply(lambda x: (x-32)/1.8) # 露点温度

    # 湿度转为浮点数，并重命名列名
    df1['humidity'] = df1['rh']/100
    df1 = df1.drop(['rh'], axis = 1)


    # 重建时间索引，因部分时间索引丢失
    new_time_index = pd.date_range(start = reset_start_time_index,
                                   end = reset_end_time_index,
                                   freq = 'H')
    df1 = df1.reindex(new_time_index, fill_value = np.nan).sort_index()
    df1.index.name = 'time'

    '''
    # 以下将逐30min数据计算为日均数据
    # df1 = df1.reset_index()
    # df1['date'] = df1['time'].dt.date
    # df1 = df1.drop(['time'], axis = 1)

    # 根据紫外线指数从大于0的时间计算当天日照时数
    # 去掉 0 ，对剩余的进行计数，单位为半小时
    def calculateSuntime(x):
        if x == 0:
            return 0
        else:
            return 0.5
    df_suntime = df1[['date', 'uv_index']].copy()
    df_suntime['uv_index'] = df_suntime['uv_index'].apply(calculateSuntime)
    df_suntime = df_suntime.groupby(['date']).sum()
    df_suntime.rename(columns = {'uv_index':'suntime'}, inplace = True)


    # 计算日均、日最大、日最小 （仅针对64位浮点类型变量）
    df_float64 = df1[['date', 'temp', 'dewPt', 'heat_index', 'pressure', 'vis', 'wc', 'wspd', 'humidity']]
    df_float64_mean = df_float64.groupby(['date']).mean()
    df_float64_mean.rename(columns={'temp':'temp_mean',
                                    'dewPt':'dewPt_mean',
                                    'heat_index':'heat_index_mean',
                                    'pressure':'pressure_mean',
                                    'vis':'vis_mean',
                                    'wc':'wc_mean',
                                    'wspd':'wspd_mean',
                                    'humidity':'humidity_mean'},
                                    inplace = True)
    df_float64_max = df_float64.groupby(['date']).max()
    df_float64_max.rename(columns={'temp':'temp_max',
                                    'dewPt':'dewPt_max',
                                    'heat_index':'heat_index_max',
                                    'pressure':'pressure_max',
                                    'vis':'vis_max',
                                    'wc':'wc_max',
                                    'wspd':'wspd_max',
                                    'humidity':'humidity_max'},
                                    inplace = True)
    df_float64_min = df_float64.groupby(['date']).min()
    df_float64_min.rename(columns={'temp':'temp_min',
                                    'dewPt':'dewPt_min',
                                    'heat_index':'heat_index_min',
                                    'pressure':'pressure_min',
                                    'vis':'vis_min',
                                    'wc':'wc_min',
                                    'wspd':'wspd_min',
                                    'humidity':'humidity_min'},
                                    inplace = True)
    df_float64_1 = pd.concat([df_float64_mean, df_float64_min, df_float64_max, df_suntime], axis = 1, verify_integrity = True)


    # 类型变量，计算当日众数
    df_object = df1[['date', 'wx_phrase', 'wdir', 'uv_desc', 'wdir_cardinal', 'clds']]
    df_object_mode = df_object.groupby(['date']).agg(lambda x: x.value_counts().index[0])
    df_object_mode.rename(columns = {'wx_phrase':'wx_phrase_mode',
                                    'wdir':'wdir_mode',
                                    'uv_desc':'uv_desc_mode',
                                    'wdir_cardinal':'wdir_cardinal_mode',
                                    'clds':'clds_mode'},
                                    inplace = True)

    # 合并数据
    df2 = pd.concat([df_float64_1, df_object_mode], axis = 1, verify_integrity = True)
    '''

    
    # 得到的数据是逐半小时的，重置索引为逐小时
    # new_index = pd.date_range('12/29/2009', periods = 10, freq = 'D')
    # df1.reindex(new_index)

    
    df1.to_csv('clean_data.csv', encoding = 'utf-8')
    os.remove('data.csv')

    return None


if __name__ == '__main__':
    req_url = 'https://api.weather.com/v1/location/ZGGG:9:CN/observations/historical.json?apiKey=e1f10a1e78da46f5b10a1e78da96f525&units=e' # 广州白云机场
    start_date = '2022-01-01'
    end_date = '2022-01-10'
    sleep_time = 6 # 最好拉长睡眠时间，太短的时间（频繁请求）回被封掉ip地址，6秒以上差不多


    #########################################################################################################################################################
    spider(req_url = req_url, sleep_time = sleep_time, start_date = start_date, end_date = end_date)
    
    if os.path.isfile('error.txt'):
        supply(req_url = req_url, sleep_time = sleep_time)
        concat_df = concat('append_data_.csv', 'data.csv')
    else:
        concat_df = pd.read_csv('data.csv', encoding = 'utf-8')

    cleanData(
        concat_df,
        reset_start_time_index = start_date + ' 00:00:00',
        reset_end_time_index = end_date + ' 00:00:00'
        )