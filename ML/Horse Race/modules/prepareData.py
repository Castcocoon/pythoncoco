import time
from unittest import skip
from urllib.request import urlopen
from tqdm.notebook import tqdm
import os
import pandas as pd
from bs4 import BeautifulSoup
import re

#raceページからのスクレイピング

def getHTMLRace(race_id_list: list,slip: bool = True):
    """
    netkeiba.comのraceページのhtmlをスクレイピングしてdata/html/raceに保存する関数
    """
    html_path_list = []
    for race_id in tqdm(race_id_list):
        url = 'https://db.netkeiba.com/race/' + race_id
        html = urlopen(url).read()
        file_name = 'data/html/race/'+ race_id + '.bin'
        html_path_list.append(file_name)
        if skip and os.path.isfile(file_name):
            print(f'race_id {race_id} skipped.')
            continue
        with open(file_name, 'wb')as f:
            f.write(html)
        time.sleep(1)
    return html_path_list

def getRawDataResults(html_path_list: list):
    """
    raceページのhtmlを受け取って、レース結果テーブルに変換する関数
    """
    race_results = {}
    for html_path in tqdm(html_path_list):
        with open(html_path, 'rb') as f:
            html = f.read()#保存してあるbinファイルを読みこむ
            df = pd.read_csv(html[0])

            soup = BeautifulSoup(html, 'html.parser')#htmlをBeautifulSoupで解析

            #馬IDを取得
            horse_id_list = []
            horse_a_list = soup.find('table', attrs = {'summary':'レース結果'}).find_all('a', attrs = {'href': re.compile('^/horse/')})
            for horse_a in horse_a_list:
                horse_id = re.findall(r'\d+', horse_a['href'])
                horse_id_list.append(horse_id[0])
            #騎手IDを取得
            jockey_id_list = []
            jockey_a_list = soup.find("table", attrs={"summary": "レース結果"}).find_all( "a", attrs={"href": re.compile("^/jockey")} )
            for jockye_a in jockey_a_list:
                jockey_id = re.findall(r'\d+', jockye_a['href'])
                jockey_id_list.append(jockey_id[0])
            
            df["horse_id"] = horse_id_list
            df["jockey_id"] = jockey_id_list
            
            #インデックスをrace_idにする
            race_id = re.findall('\d', html_path)[0]
            df.index = [race_id] * len(df)

            race_results[race_id] = df
        #pd.DataFrame型にして一つのデータにまとめる
        race_results_df = pd.concat([race_results[key] for key in race_results])
        
        return race_results_df

def getRawDataInfo(html_path_list: list):
    """
    raceページのhtmlを受け取って、レース情報(天気等)テーブルに変換する関数
    """
    race_infos = {}
    for html_path in tqdm(html_path_list):
        with open(html_path, 'rb') as f:
            html = f.read()#保存してあるbinファイルを読みこむ
            soup = BeautifulSoup(html, 'html.parser')#htmlをBeautifulSoupで解析
        #天候、レースの種類、コースの長さ、馬場の状態、日付をスクレイピング
        texts = (
            soup.find("div", attrs={"class": "data_intro"}).find_all("p")[0].text
            + soup.find("div", attrs={"class": "data_intro"}).find_all("p")[1].text
        )
        info = re.findall(r'\w+', texts)
        df = pd.Dateframe()
        for text in info:
            if text in ["芝", "ダート"]:
                df["race_type"] = [text] * len(df)
            if "障" in text:
                df["race_type"] = ["障害"] * len(df)
            if "m" in text:
                df["course_len"] = [int(re.findall(r"\d+", text)[-1])] * len(df)
            if text in ["良", "稍重", "重", "不良"]:
                df["ground_state"] = [text] * len(df)
            if text in ["曇", "晴", "雨", "小雨", "小雪", "雪"]:
                df["weather"] = [text] * len(df)
            if "年" in text:
                df["date"] = [text] 
            
        #インデックスをrace_idにする
        race_id = re.findall('\d + ', html_path)[0]
        df.index = [race_id] * len(df)

        race_infos[race_id] = df
        #pd.DataFrame型にして一つのデータにまとめる
        race_infos_df = pd.concat([race_infos[key] for key in race_infos])
    return race_infos_df

def getRaw_DataReturn(html_path_list:list):
    """
    raceページのhtmlを受け取って、払い戻しテーブルに変換する関数
    """
    return_tables = {}
    for html_path in tqdm(html_path_list):
        with open(html_path, 'rb') as f:
            html = f.read()#保存してあるbinファイルを読みこむ

            html = html.replace(b'<br />', b'br')
            dfs = pd.read_html(html)

            #dfsの1番目に単勝〜馬連、2番目にワイド〜三連単がある
            df = pd.concat([dfs[1], dfs[2]])

            race_id = re.findall('\d + ', html_path)[0]
            df.index = [race_id] * len(df)
            return_tables[race_id] = df

        #pd.DataFrame型にして一つのデータにまとめる
        return_tables_df = pd.concat([return_tables[key] for key in return_tables])
    return return_tables_df


#hourseページのスクレイピングと、競走成績のテーブル化
