import os
import glob
import re
import pandas as pd 
from datetime import datetime
import warnings
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import roc_auc_score
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

    df['賞金'].fillna(0, inplace=True)
    df.rename(columns={'着順':'着順_avg', '賞金':f'賞金_avg'}, inplace=True)
    return df

def get_average_horse_results(horse_results,horse_id_list,date,n_samples = 'all'):
    target_df = horse_results[horse_results.index.isin(horse_id_list)]
    if n_samples == 'all':
        filterd_df = target_df[target_df['date']<date]
    elif n_samples > 0:
        filterd_df = target_df[target_df['date']<date].sort_values('date',ascending=False).head(n_samples)
    else:
        raise ValueError('n_samples must be positive integer or "all"')
    
    avg_df = filterd_df.groupby(level = 0)['着順_avg', '賞金_avg'].mean()
    avg_df.rename(columns={'着順_avg':f'着順_avg_{n_samples}_R', '賞金_avg':f'賞金_avg_{n_samples}_R'}, inplace=True)

    return avg_df

def merge(race_results,race_infos,horse_results,n_samples = 'all'):
    race_results_infos = race_results.merge(race_infos,left_index=True,right_index=True,how='inner')
    race_results_infos = parse_file(race_results_infos)
    horse_results = parse_horse_file(horse_results[['日付', '着順', '賞金']])
    date_list = race_results_infos['date'].unique()
    merged_list = []
    for date in date_list:
        df = race_results_infos[race_results_infos['date'] == date]
        horse_id_list = df['horse_id']
        horse_results_avg = get_average_horse_results(horse_results,horse_id_list,date,n_samples)
        merged_df = df.merge(horse_results_avg,left_on = 'horse_id', right_index=True, how='left')
        #concatenate
        merged_list.append(merged_df)
    merged_df = pd.concat(merged_list)
    merged_df['rank'] = merged_df['着順'].map(lambda x: 1 if x < 4 else 0)
    merged_df.drop(['着順', '騎手'], axis= 1,inplace= True)
    return merged_df

def split_data(df,test_size= 0.3):
    sorted_id_list = df.sort_values(by=['date']).index.unique()
    train_id_list = sorted_id_list[:round(len(sorted_id_list)*(1-test_size))]
    test_id_list = sorted_id_list[round(len(sorted_id_list)*(1-test_size)):]
    train = df.loc[train_id_list].drop(['date'],axis=1)
    test = df.loc[test_id_list].drop(['date'],axis=1)
    return train, test

def process_category(df,category_list):
    target_df = df.copy()
    for column in category_list:
        target_df[column] = LabelEncoder().fit_transform(target_df[column].fillna('Na'))
    
    target_df = pd.get_dummies(target_df)

    for column in category_list:
        target_df[column] = df[column].astype('category')
    return target_df

class Return:
    def __init__(self,return_tables):
        self.return_tables = return_tables

    @property
    def fukusho(self):
        fukusho = self.return_tables[self.return_tables[0] == '複勝'][[1,2]]
        wins = fukusho[1].str.split('br', expand = True).drop([3], axis = 1)
        wins.columns = ['win_0', 'win_1', 'win_2']
        returns = fukusho[2].str.split('br', expand = True).drop([3], axis = 1)

        df = pd.concat([wins, returns], axis = 1)
        for column in df.columns:
            df[column] = df[column].str.replace(' ', '')
        return df.fillna(0).astype(int)
class ModelEvaluator:
    def __init__(self,model,return_tables):
        self.model = model
        self.fukusho = Return(return_tables).fukusho

    def predict_proba(self,X):
        return self.model.predict(X)[:,1]

    def predict(self,X,threshold):
        y_pred = self.predict_proba(X)
        return [0 if y < threshold else 1 for y in y_pred]

    def score(self,X,y):
        return roc_auc_score(y,self.predict_proba(X))

    def feature_importance(self,X,n_features):
        importances = pd.DataFrame({'feature':X.columns,'importance':self.model.feature_importances_})
        return importances.sort_values(by='importance',ascending=False).head(n_features)

    def predict_table(self,X,threshold = 0.5, bet_only = 0.5):
        pred_table = X.copy()
        pred_table['pred'] = self.predict(X,threshold)
        if bet_only:
            return pred_table[pred_table['pred'] == 1]['馬番']
        else:
            return pred_table

    def calculate_profit(self,X,threshold = 0.5):
        pred_table = self.predict_table(X,threshold)
        df = self.fukusho.copy()
        df = df.merge(pred_table,left_index = True, right_index=True, how='right')
        for i in range(3):
            money += df[df[f'win_{i}'] == df['馬番']][f'return_{i}'].sum()
        return money