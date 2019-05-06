"""
Pythonでgoogle financeから株価データをダウンロードするためのコード。
日本株にも対応しています。
日足だけでなく、分足も取得できます。
2018年8月から従来のgoogle finance apiが利用できなくなったため、その代替案として本コードを使用できます。
ただしダウンロードできるのは、時刻と終値だけです。出来高や始値などは取得できません。
機械学習や時系列データ分析の勉強などが目的であれば、終値データだけでも役に立つでしょう。
本コードの利用にはMIT Licenseが適用されます。
"""
import os
import time
import re
import warnings
from urllib.parse import quote_plus
import ast
import datetime
import lxml
import requests
import pandas as pd
from bs4 import BeautifulSoup
from robobrowser import RoboBrowser


class GoogleFinanceHistorical:
    def __init__(self):
        user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'
        self.browser = RoboBrowser(timeout=10, parser="lxml", user_agent=user_agent)

        # 個別銘柄のチャートページから株価データを取得するには、fw-uidが必要になる。
        # google financeのトップページにて、fw-uidを取得する。
        self.url_top = "https://www.google.com/finance"

    def get_google_finance_historical(self, market_id="/m/0cl3bc5", period="5d", interval=60 * 60 * 24):
        # 個別銘柄のチャートページから株価データを取得するには、fw-uidが必要になる。
        # google financeのトップページにて、fw-uidを取得する。
        browser = self.browser
        browser.open(self.url_top)
        # 検索フォームのei (fw-uid)を取得できるようにする。
        form = browser.get_form()
        template = "https://www.google.com/async/finance_wholepage_chart?ei={ei}&yv=3&async=mid_list:{symbolcode_encoded},period:{period},interval:{interval},extended:true,element_id:fw-uid_{ei}_1,_id:fw-uid_{ei}_1,_pms:s,_fmt:pc"
        symbolcode_encoded = quote_plus(market_id)
        url = template.format(
            ei=form["ei"].value, symbolcode_encoded=symbolcode_encoded, period=period, interval=interval)
        # 個別銘柄のチャートのデータを含むhtmlファイルを取得
        browser.open(url)
        txt = browser.response.text
        self.txt = txt


        # 正規表現を使い、株価データが記録されている部分を取り出す
        for i, str_line in enumerate(txt.splitlines()):
            if re.match("[0-9a-z]+;\[null", str_line):
                # mark_start_data = str_line[:10]
                row_to_skip = i

        self.row_to_skip = row_to_skip
        if row_to_skip != 5:
            warnings.warn("api has changed: row_to_skip = {}".format(row_to_skip))

        txt_data_list = txt.splitlines()[row_to_skip:]
        self.txt_data_list = txt_data_list
        if len(txt_data_list) != 23:
            warnings.warn("api has changed: len(txt_data_list) = {}".format(len(txt_data_list)))

        txt_data = "".join(txt_data_list)
        txt_data = re.sub("[0-9a-z]+;", "", txt_data)
        self.txt_data = txt_data
        if txt_data[:5] == '\[null':
            warnings.warn("api has changed: txt_data = {} ...".format(txt_data[:5]))

        data_list = ast.literal_eval(txt_data.replace("null", "None"))
        self.data_list = data_list
        if not isinstance(data_list, list):
            warnings.warn("type of data_list is: ".format(type(data_list)))

        str_market_info = data_list[1][0][1][0][3][0][-1][1]
        self.str_market_info = str_market_info
        if not isinstance(str_market_info, str):
            warnings.warn("type of str_market_info is: ".format(type(str_market_info)))

        historical_price_list = ast.literal_eval(str_market_info)
        self.historical_price_list_0 = historical_price_list
        if len(historical_price_list) != 16:
            warnings.warn("api has changed: len(historical_price_list) = {}".format(len(historical_price_list)))

        historical_price_list = historical_price_list[3][0][0][0][0]
        self.historical_price_list_1 = historical_price_list
        df = pd.DataFrame(historical_price_list).iloc[:, [2, 5]]
        df.columns = ["Close", "Timestamp"]

        # タイムスタンプを現地時刻に変換する
        df["Date"] = df.Timestamp.mul(60).apply(datetime.datetime.fromtimestamp)
        df["Close"] = df.Close.apply(lambda x: x[0][0])
        self.data = df.loc[:, ["Date", "Close", "Timestamp"]]


def get_google_finance_market_id(stock_symbol="NASDAQ: GOOGL"):
    """google financeの個別銘柄の識別番号(market_id)を取得する。
    Parameters
    ----------
    stock_symbol:
        個別銘柄の銘柄コード。取引市場と銘柄を指定する。
        具体例:
        NASDAQ取引所のgoogle株なら、'NASDAQ: GOOGL'とする。
        ニューヨーク証券取引所のゴールドマンサックス株なら、'NYSE: GS'とする。
        東京証券取引所のトヨタ自動車(銘柄コード7203)なら'TYO: 7203'とする。
        東京証券取引所のソフトバンク(銘柄コード9984)なら'TYO: 9984'とする。
        銘柄コードがわからない場合、https://www.google.com/financeで検索する。
        検索フォームに「トヨタ自動車」などの銘柄名を入力すると、入力補完により正確な銘柄コードを確認できる。
    Returns
    -------
    data_mid: market_id
    """
    user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'
    headers = {'User-Agent': user_agent}
    url_search = "https://www.google.{tld}/search?hl={lang}&q={query}&btnG=Google+Search&tbs={tbs}&safe={safe}&tbm={tpe}"
    query = quote_plus(stock_symbol)
    url = url_search.format(tld="com", lang="en",
                            query=query, tbs=0, safe="off", tpe="fin")
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, 'lxml')
    div_search_result = soup.find(id="search")
    div_rso = div_search_result.find(id="rso")
    eid = div_rso.attrs["eid"]
    data_mid = div_rso.div.div.attrs["data-mid"]
    return data_mid


def get_google_finance_historical(market_id="/m/0cl3bc5", period="1d", interval=60 * 60 * 24):
    """google financeから株価の終値を取得し、pandas.DataFrame形式のデータで返す。
    Parameters
    ----------
    market_id:
        google financeの個別銘柄の識別番号。どの市場のどの銘柄かを表すID。
        人間が読んでも意味が分かり難いので、get_google_finance_market_idで番号を取得するとよい。
    period:
        株価データの取得期間を文字列で指定。1d, 5d, 1Y, 3Yなど。
        '5d'は過去5日間のデータ、'3Y'は過去3年間のデータを取得する。
        確認できている限りでは、日足では過去5年間、1分足では過去21日間、5分足では過去３ヶ月間のデータを取得できた。
        この期間を過度に長くすると、データの取得に失敗する。
    interval:
        株価データのインターバルを整数で指定。単位は秒。
        例えば、日足を取得したいなら60 * 60 * 24とし、5分足なら60 * 5
        最小が60(1分足よりも短いインターバルの株価は取得できない)。
    Returns
    -------
    df: pandas.DataFrame形式データ。
        カラム名のDateは株価が付いたときの現地時刻、Closeは終値を表す。
    備考
    ----
    google financeの株価チャートに表示される株価データ(終値)をweb scrapingして、
    現地時刻と終値を正規表現を使って取得する。
    もとのデータに、終値以外の価格が記録されていないため、OHLCVデータのうちClose(終値)のみしか取得できない。
    株価データが記載されているhtmlファイルでの該当部分のフォーマットが変更された場合、assert文でエラーがでる。
    assert文でエラーが出た場合、引数が不敵切なのではなく、google financeの仕様がかわったと判断する。
    """
    user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'
    browser = RoboBrowser(timeout=10, parser="lxml", user_agent=user_agent)

    # 個別銘柄のチャートページから株価データを取得するには、fw-uidが必要になる。
    # google financeのトップページにて、fw-uidを取得する。
    url_top = "https://www.google.com/finance"
    browser.open(url_top)
    # 検索フォームのei (fw-uid)を取得できるようにする。
    form = browser.get_form()
    template = "https://www.google.com/async/finance_wholepage_chart?ei={ei}&yv=3&async=mid_list:{symbolcode_encoded},period:{period},interval:{interval},extended:true,element_id:fw-uid_{ei}_1,_id:fw-uid_{ei}_1,_pms:s,_fmt:pc"
    symbolcode_encoded = quote_plus(market_id)
    url = template.format(
        ei=form["ei"].value, symbolcode_encoded=symbolcode_encoded, period=period, interval=interval)
    # 個別銘柄のチャートのデータを含むhtmlファイルを取得
    browser.open(url)
    txt = browser.response.text

    # 正規表現を使い、株価データが記録されている部分を取り出す
    for i, str_line in enumerate(txt.splitlines()):
        if re.match("[0-9a-z]+;\[null", str_line):
            # mark_start_data = str_line[:10]
            row_to_skip = i
            assert row_to_skip == 4

    txt_data_list = txt.splitlines()[row_to_skip:]
    assert len(txt_data_list) == 17
    txt_data = "".join(txt_data_list)
    txt_data = re.sub("[0-9a-z]+;", "", txt_data)
    assert txt_data[:5] == '[null'

    data_list = ast.literal_eval(txt_data.replace("null", "None"))
    assert isinstance(data_list, list)

    str_market_info = data_list[1][0][1][0][3][0][-1][1]
    assert isinstance(str_market_info, str)
    historical_price_list = ast.literal_eval(str_market_info)
    assert len(historical_price_list) == 4

    historical_price_list = historical_price_list[0][2][0][0]
    assert len(historical_price_list[0]) == 5

    df = pd.DataFrame(historical_price_list, columns=[
                      "A", "B", "Close", "Pct", "Timestamp"])
    # タイムスタンプを現地時刻に変換する
    df["Date"] = df.Timestamp.mul(60).apply(datetime.datetime.fromtimestamp)
    df["Close"] = df.Close.str.replace(",", "").apply(float)
    return df.loc[:, ["Date", "Close", "Timestamp"]]


def download_multi_symbols(symbol_list=[7203, 9984], period="3Y", interval=60 * 60 * 24, pause=1, folderpath="stockdata"):
    """複数銘柄の日本株の株価データをgoogle financeからダウンロードしてcsv形式で保存
    csvファイルのファイル名には、ダウンロード日時と銘柄コードを付ける。
    symbol_list:
        日本株の銘柄コードのリスト。銘柄コードのTYOは省略する。
    period:
        株価データの取得期間を文字列で指定。1d, 5d, 1Y, 3Yなど。
        '5d'は過去5日間のデータ、'3Y'は過去3年間のデータを取得する。
        確認できている限りでは、日足では過去5年間、1分足では過去21日間、5分足では過去３ヶ月間のデータを取得できた。
        この期間を過度に長くすると、データの取得に失敗する。
    interval:
        株価データのインターバルを整数で指定。単位は秒。
        例えば、日足を取得したいなら60 * 60 * 24とし、5分足なら60 * 5
        最小が60(1分足よりも短いインターバルの株価は取得できない)。
    pause:
        銘柄1つのダウンロードごとの待ち時間。秒単位。
        大量のデータをダウンロードする場合、待ち時間が短いとサーバーへのアクセスをブロックされる。
    folderpath:
        csvファイルの保存先のフォルダのパス。該当するフォルダが無ければカレントディレクトリに新規作成する。
    """
    str_datetime_today = datetime.datetime.today().strftime('%Y-%m-%d_%H')
    filename_tempplate = "{str_datetime_today}_{symbol_code}.csv"
    if not os.path.exists(folderpath):
        os.mkdir(folderpath)

    for i in symbol_list:
        stock_symbol = "TYO: {symbol_code}".format(symbol_code=i)
        market_id = get_google_finance_market_id(stock_symbol)
        google = GoogleFinanceHistorical()
        google.get_google_finance_historical(market_id, period=period, interval=interval)
        df = google.data
        df["Symbol_Code"] = i

        filename = filename_tempplate.format(str_datetime_today=str_datetime_today, symbol_code=i)
        filepath = os.path.join(folderpath, filename)
        df.to_csv(filepath, index=False)
        time.sleep(pause)


if __name__ == "__main__":
    # Googleのmarket_idを取得する
    market_id_google = get_google_finance_market_id("NASDAQ: GOOG")
    # Googleの株価データを取得する。過去5年間の日足の終値をpandas.Dataframeのデータで得る。
    df_google_daily = get_google_finance_historical(market_id_google, period="5Y", interval=60 * 60 * 24)
    # Googleの株価データを取得する。過去3日間の5分足の終値をpandas.Dataframeのデータで得る。
    df_google_5minutes = get_google_finance_historical(market_id_google, period="3d", interval=60 * 5)

    # トヨタ自動車の株価データを取得する(銘柄コード7203)
    market_id = get_google_finance_market_id("TYO: 7203")
    # 過去5年間の日足の終値
    df_toyota_daily = get_google_finance_historical(market_id, period="5Y", interval=60 * 60 * 24)
    # 過去5日間の5分足の終値
    df_toyota_5minutes = get_google_finance_historical(market_id, period="5d", interval=60 * 5)
