import os
import glob
import pandas as pd 
from datetime import datetime
import warnings
warnings.filterwarnings("ignore")


def get_file_path():
    files = glob.glob('data/raw/*/*.pickle')
    return files

def get_file_name(file_path):
    file_name = os.path.splitext(os.path.basename(file_path))[0]
    return file_name

def parse_file(race_results):
    df = race_results.copy()
    # 着順に数字以外の文字列が含まれているものを取り除く
    df = df[~(df['着順'].astype(str).str.contains('\D'))]
    df['着順']= df['着順'].astype(int)

    #性齢を性と年齢に分割
    df['性']= df['性齢'].map(lambda x: str(x)[0])
    df['齢']= df['性齢'].map(lambda x: str(x)[1:]).astype(int)
    
    # #馬体重を体重と体重変化に分割
    df['体重']= df['馬体重'].str.split('(').str[0].astype(int)
    df['体重変化']= df['馬体重'].str.split('(').str[1].str.split(')').str[0].astype(int)
    
    #データをfloat型に変換
    df['単勝']= df['単勝'].astype(float)
    
    #いらない列を削除
    df = df.drop(['タイム', '着差', '調教師', '性齢', '馬体重'], axis=1)
    
    df['date'] = pd.to_datetime(df['date'], format='%Y年%m月%d日')
    
    return df

def parse_horse_file(horse_results):
    df = horse_results.copy()
    # 着順に数字以外の文字列が含まれているものを取り除く
    df['着順'] = pd.to_numeric(df['着順'], errors='coerce')
    df.dropna(subset = ['着順'], inplace=True)
    df['着順']= df['着順'].astype(int)

    df['date'] = pd.to_datetime(df['日付'])
    df.drop(['日付'], axis=1, inplace=True) 
    df.rename(columns={'着順':'着順_avg', '賞金':'賞金_avg'}, inplace=True)
    return df

def get_average_horse_results(horse_results,horse_id_list,date):
    target_df = horse_results[horse_results.index.isin(horse_id_list)]
    target_df = target_df[target_df['date']<date].groupby(level = 0)['着順_avg', '賞金_avg'].mean()
    return target_df

def merge(race_results,race_infos,horse_results):
    race_results_infos = race_results.merge(race_infos,left_index=True,right_index=True,how='inner')
    race_results_infos = parse_file(race_results_infos)
    horse_results = parse_horse_file(horse_results[['日付', '着順', '賞金']])
    date_list = race_results_infos['date'].unique()
    merged_list = []
    for date in date_list:
        df = race_results_infos[race_results_infos['date'] == date]
        horse_id_list = df['horse_id']
        horse_results_avg = get_average_horse_results(horse_results,horse_id_list,date)
        merged_df = df.merge(horse_results_avg,left_on = 'horse_id', right_index=True, how='left')
        #concatenate
        merged_list.append(merged_df)
    merged_df = pd.concat(merged_list)
    return merged_df

def split_data(df,test_size= 0.3):
    sorted_id_list = df.sort_values(by=['date']).index.unique()
    train_id_list = sorted_id_list[:round(len(sorted_id_list)*(1-test_size))]
    test_id_list = sorted_id_list[round(len(sorted_id_list)*(1-test_size)):]
    train = df.loc[train_id_list]
    test = df.loc[test_id_list]
    return train, test
