from collections import OrderedDict

import random
import string
import unicodedata

from difflib import SequenceMatcher


def unique_stack_list(stack_list):
    seen = set()
    unique_list = []
    for stack in stack_list:
        stack_hash = stack['hash']
        if stack_hash in seen:
            continue
        unique_list.append(stack)
        seen.add(stack_hash)
    return unique_list


def unique_hashable(hashable_items):
    """Removes duplicates from the list. Must preserve the orders."""
    return list(OrderedDict.fromkeys(hashable_items))


def get_random_str(n):
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for i in range(n))


def get_non_rec_text(element):
    """
    input:
      element: bs4 の要素オブジェクト
    Output:
      [0]: ↓で得られる str。
    Note: 
      まず、element.find_all によって「element の子要素(孫は含まない)の全てのテキスト」が取り出される。
      引数 text は現在の引数 string の旧称で、recursive=False は孫は見ないよって意味。
      https://www.crummy.com/software/BeautifulSoup/bs4/doc/#find-all
      そしてそれを "".join() で連結させて 1 つの文字列にして、両端の空白や改行をカットする。
    """
    return ''.join(element.find_all(text=True, recursive=False)).strip()


def normalize(item):
    """
    input:
      item: なんらかの文字列? もし文字列じゃない場合はそのまま return されるので。
    Output:  
      [0]: item に以下の変換処理を加えた文字列。
           - 両端の連続する 空白(半スペ), 改行(\n), タブ(\t) を除去する。
             例：`"\n  \n abc \t \t\t  ".strip()`
           - 文字列の正規化 (意味は同じだが半角全角などのフォーマットが異なるやつを統一する) を行う。
             例：`unicodedata.normalize("NFKD", "アｱ  平成㍻  1１①  ,，.．  ａa")`
    """
    if not isinstance(item, str):
    # item が str 型オブジェクトではない場合
        return item
        # そのまま返す
    return unicodedata.normalize("NFKD", item.strip())
    # NFKD形式に統一するような正規化。


def text_match(t1, t2, ratio_limit):
    """
    input:
      t1: テキスト1 (正規表現パターンオブジェクトの時もある?)
      t2: テキスト2
      ratio_limit: 類似度に対する閾値
    """
    if hasattr(t1, 'fullmatch'):
    # もし t1 が属性(メソッド)として fullmatch を持っていれば、
    # これはつまり t1 が正規表現パターンオブジェクト (re.compile("pattern")で作られるやつ) てこと？
        return bool(t1.fullmatch(t2))
        # 文字列 t2 の全体が、正規表現パターン t1 にマッチするかどうか、の True, False をリターン
        # https://note.nkmk.me/python-re-regex-character-type/
    if ratio_limit >= 1:
        return t1 == t2
        # (t1が正規表現パターンオブジェクトではなくて) ratio_limit に 1 以上が設定されてる場合、
        # t1 と t2 が文字列として完全一致しているかどうか、の True, False をリターン
    return SequenceMatcher(None, t1, t2).ratio() >= ratio_limit
    # 文字列 t1, t2 をゲシュタルトパターンマッチングで比較して類似度を算出。
    # その類似度(最大1)が ratio_limit 以上であれば True, そうでなければ False を返す。
    # (第一引数 None は比較で無視する文字列)
    # ここに比較方法を変えれば、別のアルゴリズムになる。日本語ブログに特化した matcher 使うとか。
    # http://pixelbeat.jp/text-matching-3-approach-with-python/#toc_id_2
    # https://qiita.com/aizakku_nidaa/items/20abcd8aa32152786687
    # https://blog.mudatobunka.org/entry/2016/05/08/154934
    # https://docs.python.org/ja/3/library/difflib.html



class ResultItem():
    def __init__(self, text, index):
        self.text = text
        self.index = index

    def __str__(self):
        return self.text


class FuzzyText(object):
    def __init__(self, text, ratio_limit):
        self.text = text
        self.ratio_limit = ratio_limit
        self.match = None

    def search(self, text):
        return SequenceMatcher(None, self.text, text).ratio() >= self.ratio_limit
