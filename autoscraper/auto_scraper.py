import hashlib
import json

from collections import defaultdict
from html import unescape
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from autoscraper.utils import get_random_str, unique_hashable, unique_stack_list, \
    ResultItem, FuzzyText, get_non_rec_text, text_match, normalize
# import autoscraper.utils
# autoscraper.utils.__file__
# このローカルリポジトリの autoscraper からではなく pip でインストールしたオリジナルの autoscraper からインポートしてる。




class AutoScraper(object):
    """
    AutoScraper : A Smart, Automatic, Fast and Lightweight Web Scraper for Python.
    AutoScraper automatically learns a set of rules required to extract the needed content
        from a web page. So the programmer doesn't need to explicitly construct the rules.
    ↓
    Python 用のスマートで自動で高速で軽量なウェブスクレイパー。
    AutoScraper はウェブページから必要なコンテンツを抽出するための一連のルールを自動的に学習する。
    そのため、プログラマは明示的にルールを構築する必要はありません。
    まさに今回目指してる形。

    Attributes
    ----------
    stack_list: list
        List of rules learned by AutoScraper
    ↓
    学習されたルールのリスト。
    そもそも AutoScraper はどういう「ルール」を作るのだろうか。
    XPath なのか CSS セレクタなのか、なんだろうか。

    Methods
    -------
    build() - Learns a set of rules represented as stack_list based on the wanted_list,
        which can be reused for scraping similar elements from other web pages in the future.
    ↓
    抽出ルールの学習：
    wanted_list (引数で渡す正解ラベル) をもとに抽出ルールを作成して stack_list 属性に格納する。
    そのルールは、他のウェブページから同じ要素をスクレイピングするのにも使える。
    
    get_result_similar() - Gets similar results based on the previously learned rules.
    ↓
    学習済みのルールによる抽出(曖昧ver)：
    次のメソッドの対比からしてこういう感じかな。詳細はメソッド定義の docstring 
    
    get_result_exact() - Gets exact results based on the previously learned rules.
    ↓
    学習済みのルールによる抽出(厳密ver)：
    チュートリアルでも紹介されてたやつ。
    
    get_results() - Gets exact and similar results based on the previously learned rules.
    ↓
    学習済みのルールによる抽出(両方ver)：

    save() - Serializes the stack_list as JSON and saves it to disk.

    load() - De-serializes the JSON representation of the stack_list and loads it back.
    ↓

    remove_rules() - Removes one or more learned rule[s] from the stack_list.
    ↓
    学習済みルールの削除(消すものを指定)

    keep_rules() - Keeps only the specified learned rules in the stack_list and removes the others.
    ↓
    学習済みルールの削除(残すものを指定)

    """

    request_headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/537.36 \
            (KHTML, like Gecko) Chrome/84.0.4147.135 Safari/537.36'
    }
    # init の外なので、インスタンス属性ではなくてクラス属性であることに注意。
    # そのため、インスタンス生成してなくても、AutoScraper.request_headers で参照可能。
    # ちなみに、インスタンスからも autoscraper.request_headers と参照できる。
    # 意味は未理解。http 通信のリクエストのヘッダー情報？


    def __init__(self, stack_list=None):
        self.stack_list = stack_list or []
        # or の面白い使い方。
        # stack_list が None ならば右辺の [] 、None でなければ左辺の stack_list となる
        # まあ最初からデフォルト値を stack_list=[] として self.stack_list = stack_list とした方が分かりやすい。


    def save(self, file_path):
        """
        Serializes the stack_list as JSON and saves it to the disk.
        学習済みのルールの保存

        Parameters
        ----------
        file_path: str
            Path of the JSON output

        Returns
        -------
        None
        """

        data = dict(stack_list=self.stack_list)
        with open(file_path, 'w') as f:
            json.dump(data, f)
        # 辞書にした上で JSON に出力するっていう定番の方法。
        # stack_list の形式はまだ不明。


    def load(self, file_path):
        """
        De-serializes the JSON representation of the stack_list and loads it back.
        学習済みのルールの読み込み：
        save() と合わせて使うのかな基本。
        それかまあ、人手で作ったルールを読み込ませる、って風にも使えるか。
        この機能は必要なので研究でも採用したい。

        Parameters
        ----------
        file_path: str
            Path of the JSON file to load stack_list from.

        Returns
        -------
        None
        """

        with open(file_path, 'r') as f:
            data = json.load(f)
        # JSON を dict に読み込む一般的な方法。

        # for backward compatibility
        # 後方互換性(前のバージョンてこと？)のための if 文
        if isinstance(data, list):
            self.stack_list = data
            return

        self.stack_list = data['stack_list']
        # ファイルから読み込んだ抽出ルールをちゃんと stack_list 属性に入れてる


    @classmethod
    def _get_soup(cls, url=None, html=None, request_args=None):
        """
        Input:
          cls: クラスメソッドなので自動的にクラスオブジェクト AutoScraper が渡される(後述)。
          url: BeautifulSoup オブジェクトに変換したいページの URL。
          html: BeautifulSoup オブジェクトに変換したい HTML ソース。
          request_args: Web サーバに URL で指定したページをリクエストする際のオプション?
        Output:
          [0]: 入力で指定された(URLの)htmlを前処理した上でBeautifulSoupインスタンスに変換したやつ
        Note:
          @classmethod と @staticmethod デコレータについて
          ここには @classmethod というデコレータがついているので、これはクラスメソッド。
          クラスメソッドとは、さっきのクラス変数 request_headers と同じ感じで、
          クラスオブジェクト AutoScraper からもインスタンスオブジェクト autoscraper からも
          両方から参照できるようなメソッド。
          __init__() で自動的に第一引数にインスタンスが渡される(名前は通常self)ように、
          クラスメソッドでは自動的に第一引数にクラスが渡される(名前は通常clsにする)。
          そのため、↓で cls.request_headers と参照できている。
          一方、この次のメソッドのように @staticmethod がついてると、スタティックメソッドとなる。
          staticmethod は classmethod とほぼ同じだが、
          唯一違うのは、staticmethod では第一引数にクラスオブジェクトが渡されないこと。
          つまり staticmethod ではクラスオブジェクトを参照することができないこと。
          両者の違いと使い分けについては、
          - https://www.sejuku.net/blog/25130
          - https://python.ms/classmethod-and-staticmethod/
          - https://qiita.com/ysk24ok/items/848daec3886f1030f587
        """

        request_args = request_args or {}
        # デフォルト値として {} を設定したのと等価。

        if html:
            html = normalize(unescape(html))
            return BeautifulSoup(html, 'lxml')
            # 引数htmlに HTML ソース文字列が渡されていた場合、
            # unescape() で、タグとの区別のために &gt, &lt にエスケープされてた  >, < を元に戻して、`unescape("x &lt y")`
            # utils.py 定義の normalize() でユニコード正規化等をして、
            # BeautifulSoup オブジェクトに変換して、
            # 返す。

        headers = dict(cls.request_headers)
        # クラス属性 request_headers を headers に入れる。
        if url:
            headers['Host'] = urlparse(url).netloc
            # 引数 url に URL が与えられてる時、
            # URL を解析してパーツに切り分けて、FQDN(ホスト名+ドメイン名)を取得してる。https://livra.geolocation.co.jp/iplearning/250/
            # URL の構成の勉強にもなる。具体的には↓
            # urlparse("https://www.dtvcl.com/product/datadiver/")
            # urlparse("https://www.dtvcl.com/download/?category=dataDiver")
            # urlparse("https://違い.net/programing/#:~:text=「オブジェクト」とは、目,持つ「オブジェクト」の集合。")

        user_headers = request_args.pop('headers', {})
        headers.update(user_headers)
        # 引数 request_args に "headers" メンバが入っていたら、
        # それを取り出して、この関数で作った headers に追加(or上書き)する。

        html = requests.get(url, headers=headers, **request_args).text
        html = normalize(unescape(html))
        # 引数の URL のページを Web サーバーにリクエストして取得して HTML ソース文字列にする。
        # (ここまでで作ったヘッダー情報やリクエストの他のパラメータも渡しつつ)
        # さらに、
        # unescape() で、タグとの区別のために &gt, &lt にエスケープされてた  >, < を元に戻して、`unescape("x &lt y")`
        # utils.py 定義の normalize() でユニコード正規化等をして、
        # ↓でBeautifulSoup オブジェクトに変換して、
        # 返す。

        return BeautifulSoup(html, 'lxml')

    
    @staticmethod
    def _get_valid_attrs(item):
        """
        input:
          item: 属性 item.attrs に辞書を持つようなオブジェクト (bs4関連?)
        output:
          [0]: item.attrs から "class", "style" メンバを取り出し、
               もしメンバがなかったり値が空だった場合はそこを補完したような辞書。
        Note:
          この output をスクレイピングルールの判定に使うのか？だから形式を揃えている感じか？
          @staticmethod については _get_soup() の docs 参照。
        """
        key_attrs = {'class', 'style'}
        attrs = {
            k: v if v != [] else '' for k, v in item.attrs.items() if k in key_attrs
        }
        # 辞書内包表記
        # 原型は `{k: v for k, v in item.attrs.items()}` で、
        # このままだと item.attrs をコピーした辞書を作るだけなので、そこに色々条件をくっつけた感じ。
        # まず、後ろの `if k in key_attrs` によって、
        # 「そもそも k (辞書のキー) が key_attrs("class"と"style") に含まれない時は処理しない」
        # って感じになる。なので結局 item.attrs の "class", "style" メンバだけを処理するてこと。
        # で、前半の `v if v != [] else ''` によって、
        # 処理対象の v が空リスト[] の時は "" が作られてそうでない時はそのまま移される。
        # まとめると結局「item.attrs の class, style メンバだけの辞書を作って値が[]だったら""にする」
        # てのをやってる。
        # 注意点としては、もし item.attrs に "class", "style" がなくてもエラーにならない。

        for attr in key_attrs:
            if attr not in attrs:
                attrs[attr] = ''
        # 先ほど item.attrs に "class" や "style" がなくて attrs にもそれが欠けてしまった場合、
        # そこを値が空なメンバにして埋めてあげる。
        return attrs

    
    @staticmethod
    def _child_has_text(child, text, url, text_fuzz_ratio):
        """
        input:
          child: 多分 bs4 の要素オブジェクト(タブオブジェクト)。
          text: テキスト
        """
        child_text = child.getText().strip()
        # bs4 要素(タグ)オブジェクト child から値(テキスト)を取り出して、両端の空白や改行を削除する。
        # getText は昔のメソッド名で今は get_text らしい。

        if text_match(text, child_text, text_fuzz_ratio):
            # text(文字列かREパターン?)が child のテキストと閾値 text_fuzz_ratio で類似している場合、
            # まず、child の親要素のテキストを取り出す。
            # もしそれが child のテキストと完全一致していたら、False をリターンする。
            # (子じゃなくて親が text を持っている、という意味の False ?)
            # 逆に、もしそれが chile のテキストと完全一致していなかったら、True をリターンする。(child.wanted_attr=None した上で)
            # (親じゃなくてちゃんと子が text を持っている、という意味の True?)
            parent_text = child.parent.getText().strip()
            if child_text == parent_text:
                return False

            child.wanted_attr = None
            return True

        if text_match(text, get_non_rec_text(child), text_fuzz_ratio):
            child.is_non_rec_text = True
            child.wanted_attr = None
            return True

        for key, value in child.attrs.items():
            if not isinstance(value, str):
                continue

            value = value.strip()
            if text_match(text, value, text_fuzz_ratio):
                child.wanted_attr = key
                return True

            if key in {'href', 'src'}:
                full_url = urljoin(url, value)
                if text == full_url:
                    child.wanted_attr = key
                    child.is_full_url = True
                    return True

        return False

    def _get_children(self, soup, text, url, text_fuzz_ratio):
        children = reversed(soup.findChildren())
        children = [x for x in children if self._child_has_text(x, text, url, text_fuzz_ratio)]
        return children

    def build(self, url=None, wanted_list=None, wanted_dict=None, html=None, request_args=None,
              update=False, text_fuzz_ratio=1.0):
        """
        Automatically constructs a set of rules to scrape the specified target[s] from a web page.
            The rules are represented as stack_list.

        Parameters:
        ----------
        url: str, optional
            URL of the target web page. You should either pass url or html or both.

        wanted_list: list of strings or compiled regular expressions, optional
            A list of needed contents to be scraped.
                AutoScraper learns a set of rules to scrape these targets. If specified,
                wanted_dict will be ignored.
        
        wanted_dict: dict, optional
            A dict of needed contents to be scraped. Keys are aliases and values are list of target texts
                or compiled regular expressions.
                AutoScraper learns a set of rules to scrape these targets and sets its aliases.

        html: str, optional
            An HTML string can also be passed instead of URL.
                You should either pass url or html or both.

        request_args: dict, optional
            A dictionary used to specify a set of additional request parameters used by requests
                module. You can specify proxy URLs, custom headers etc.

        update: bool, optional, defaults to False
            If True, new learned rules will be added to the previous ones.
            If False, all previously learned rules will be removed.

        text_fuzz_ratio: float in range [0, 1], optional, defaults to 1.0
            The fuzziness ratio threshold for matching the wanted contents.

        Returns:
        --------
        List of similar results
        """

        soup = self._get_soup(url=url, html=html, request_args=request_args)

        result_list = []

        if update is False:
            self.stack_list = []

        if wanted_list:
            wanted_dict = {'': wanted_list}

        wanted_list = []

        for alias, wanted_items in wanted_dict.items():
            wanted_items = [normalize(w) for w in wanted_items]
            wanted_list += wanted_items

            for wanted in wanted_items:
                children = self._get_children(soup, wanted, url, text_fuzz_ratio)

                for child in children:
                    result, stack = self._get_result_for_child(child, soup, url)
                    stack['alias'] = alias
                    result_list += result
                    self.stack_list.append(stack)

        result_list = [item.text for item in result_list]
        result_list = unique_hashable(result_list)

        self.stack_list = unique_stack_list(self.stack_list)
        return result_list

    @classmethod
    def _build_stack(cls, child, url):
        content = [(child.name, cls._get_valid_attrs(child))]

        parent = child
        while True:
            grand_parent = parent.findParent()
            if not grand_parent:
                break

            children = grand_parent.findAll(parent.name, cls._get_valid_attrs(parent),
                                                         recursive=False)
            for i, c in enumerate(children):
                if c == parent:
                    content.insert(
                        0, (grand_parent.name, cls._get_valid_attrs(grand_parent), i))
                    break

            if grand_parent.name == 'html':
                break

            parent = grand_parent

        wanted_attr = getattr(child, 'wanted_attr', None)
        is_full_url = getattr(child, 'is_full_url', False)
        is_non_rec_text = getattr(child, 'is_non_rec_text', False)
        stack = dict(content=content, wanted_attr=wanted_attr, is_full_url=is_full_url,
                     is_non_rec_text=is_non_rec_text)
        stack['url'] = url if is_full_url else ''
        stack['hash'] = hashlib.sha256(str(stack).encode('utf-8')).hexdigest()
        stack['stack_id'] = 'rule_' + get_random_str(4)
        return stack

    def _get_result_for_child(self, child, soup, url):
        stack = self._build_stack(child, url)
        result = self._get_result_with_stack(stack, soup, url, 1.0)
        return result, stack

    @staticmethod
    def _fetch_result_from_child(child, wanted_attr, is_full_url, url, is_non_rec_text):
        if wanted_attr is None:
            if is_non_rec_text:
                return get_non_rec_text(child)
            return child.getText().strip()

        if wanted_attr not in child.attrs:
            return None

        if is_full_url:
            return urljoin(url, child.attrs[wanted_attr])

        return child.attrs[wanted_attr]

    @staticmethod
    def _get_fuzzy_attrs(attrs, attr_fuzz_ratio):
        attrs = dict(attrs)
        for key, val in attrs.items():
            if isinstance(val, str) and val:
                val = FuzzyText(val, attr_fuzz_ratio)
            elif isinstance(val, (list, tuple)):
                val = [FuzzyText(x, attr_fuzz_ratio) if x else x for x in val]
            attrs[key] = val
        return attrs

    def _get_result_with_stack(self, stack, soup, url, attr_fuzz_ratio, **kwargs):
        parents = [soup]
        stack_content = stack['content']
        contain_sibling_leaves = kwargs.get('contain_sibling_leaves', False)
        for index, item in enumerate(stack_content):
            children = []
            for parent in parents:

                attrs = item[1]
                if attr_fuzz_ratio < 1.0:
                    attrs = self._get_fuzzy_attrs(attrs, attr_fuzz_ratio)

                found = parent.findAll(item[0], attrs, recursive=False)
                if not found:
                    continue

                if not contain_sibling_leaves and index == len(stack_content) - 1:
                    idx = min(len(found) - 1, stack_content[index - 1][2])
                    found = [found[idx]]

                children += found

            parents = children

        wanted_attr = stack['wanted_attr']
        is_full_url = stack['is_full_url']
        is_non_rec_text = stack.get('is_non_rec_text', False)
        result = [ResultItem(self._fetch_result_from_child(i, wanted_attr,
                              is_full_url, url, is_non_rec_text),
                              getattr(i, 'child_index', 0)) for i in parents]
        result = [x for x in result if x.text]
        return result

    def _get_result_with_stack_index_based(self, stack, soup, url, attr_fuzz_ratio, **kwargs):
        p = soup.findChildren(recursive=False)[0]
        stack_content = stack['content']
        for index, item in enumerate(stack_content[:-1]):
            content = stack_content[index + 1]
            attrs = content[1]
            if attr_fuzz_ratio < 1.0:
                attrs = self._get_fuzzy_attrs(attrs, attr_fuzz_ratio)
            p = p.findAll(content[0], attrs, recursive=False)
            if not p:
                return []
            idx = min(len(p) - 1, item[2])
            p = p[idx]

        result = [ResultItem(self._fetch_result_from_child(
            p, stack['wanted_attr'], stack['is_full_url'], url, stack['is_non_rec_text']),
            getattr(p, 'child_index', 0))]
        result = [x for x in result if x.text]
        return result

    def _get_result_by_func(self, func, url, html, soup, request_args, grouped,
                            group_by_alias, unique, attr_fuzz_ratio, **kwargs):
        if not soup:
            soup = self._get_soup(url=url, html=html, request_args=request_args)

        keep_order = kwargs.get('keep_order', False)

        if group_by_alias or (keep_order and not grouped):
            for index, child in enumerate(soup.findChildren()):
                setattr(child, 'child_index', index)

        result_list = []
        grouped_result = defaultdict(list)
        for stack in self.stack_list:
            if not url:
                url = stack.get('url', '')

            result = func(stack, soup, url, attr_fuzz_ratio, **kwargs)

            if not grouped and not group_by_alias:
                result_list += result
                continue

            group_id = stack.get('alias', '') if group_by_alias else stack['stack_id']
            grouped_result[group_id] += result

        return self._clean_result(result_list, grouped_result, grouped, group_by_alias,
                                  unique, keep_order)

    @staticmethod
    def _clean_result(result_list, grouped_result, grouped, grouped_by_alias, unique, keep_order):
        if not grouped and not grouped_by_alias:
            if unique is None:
                unique = True
            if keep_order:
                result_list = sorted(result_list, key=lambda x: x.index)
            result = [x.text for x in result_list]
            if unique:
                result = unique_hashable(result)
            return result

        for k, val in grouped_result.items():
            if grouped_by_alias:
                val = sorted(val, key=lambda x: x.index)
            val = [x.text for x in val]
            if unique:
                val = unique_hashable(val)
            grouped_result[k] = val

        return dict(grouped_result)

    def get_result_similar(self, url=None, html=None, soup=None, request_args=None,
                           grouped=False, group_by_alias=False, unique=None, attr_fuzz_ratio=1.0,
                           keep_order=False, contain_sibling_leaves=False):
        """
        Gets similar results based on the previously learned rules.

        Parameters:
        ----------
        url: str, optional
            URL of the target web page. You should either pass url or html or both.

        html: str, optional
            An HTML string can also be passed instead of URL.
                You should either pass url or html or both.

        request_args: dict, optional
            A dictionary used to specify a set of additional request parameters used by requests
                module. You can specify proxy URLs, custom headers etc.

        grouped: bool, optional, defaults to False
            If set to True, the result will be a dictionary with the rule_ids as keys
                and a list of scraped data per rule as values.

        group_by_alias: bool, optional, defaults to False
            If set to True, the result will be a dictionary with the rule alias as keys
                and a list of scraped data per alias as values.

        unique: bool, optional, defaults to True for non grouped results and
                False for grouped results.
            If set to True, will remove duplicates from returned result list.

        attr_fuzz_ratio: float in range [0, 1], optional, defaults to 1.0
            The fuzziness ratio threshold for matching html tag attributes.

        keep_order: bool, optional, defaults to False
            If set to True, the results will be ordered as they are present on the web page.

        contain_sibling_leaves: bool, optional, defaults to False
            If set to True, the results will also contain the sibling leaves of the wanted elements.

        Returns:
        --------
        List of similar results scraped from the web page.
        Dictionary if grouped=True or group_by_alias=True.
        """

        func = self._get_result_with_stack
        return self._get_result_by_func(func, url, html, soup, request_args, grouped,
                                         group_by_alias, unique, attr_fuzz_ratio,
                                         keep_order=keep_order,
                                         contain_sibling_leaves=contain_sibling_leaves)

    def get_result_exact(self, url=None, html=None, soup=None, request_args=None,
                         grouped=False, group_by_alias=False, unique=None, attr_fuzz_ratio=1.0):
        """
        Gets exact results based on the previously learned rules.

        Parameters:
        ----------
        url: str, optional
            URL of the target web page. You should either pass url or html or both.

        html: str, optional
            An HTML string can also be passed instead of URL.
                You should either pass url or html or both.

        request_args: dict, optional
            A dictionary used to specify a set of additional request parameters used by requests
                module. You can specify proxy URLs, custom headers etc.

        grouped: bool, optional, defaults to False
            If set to True, the result will be a dictionary with the rule_ids as keys
                and a list of scraped data per rule as values.

        group_by_alias: bool, optional, defaults to False
            If set to True, the result will be a dictionary with the rule alias as keys
                and a list of scraped data per alias as values.

        unique: bool, optional, defaults to True for non grouped results and
                False for grouped results.
            If set to True, will remove duplicates from returned result list.

        attr_fuzz_ratio: float in range [0, 1], optional, defaults to 1.0
            The fuzziness ratio threshold for matching html tag attributes.

        Returns:
        --------
        List of exact results scraped from the web page.
        Dictionary if grouped=True or group_by_alias=True.
        """

        func = self._get_result_with_stack_index_based
        return self._get_result_by_func(func, url, html, soup, request_args, grouped,
                                        group_by_alias, unique, attr_fuzz_ratio)

    def get_result(self, url=None, html=None, request_args=None, grouped=False,
                   group_by_alias=False, unique=None, attr_fuzz_ratio=1.0):
        """
        Gets similar and exact results based on the previously learned rules.

        Parameters:
        ----------
        url: str, optional
            URL of the target web page. You should either pass url or html or both.

        html: str, optional
            An HTML string can also be passed instead of URL.
                You should either pass url or html or both.

        request_args: dict, optional
            A dictionary used to specify a set of additional request parameters used by requests
                module. You can specify proxy URLs, custom headers etc.

        grouped: bool, optional, defaults to False
            If set to True, the result will be dictionaries with the rule_ids as keys
                and a list of scraped data per rule as values.

        group_by_alias: bool, optional, defaults to False
            If set to True, the result will be a dictionary with the rule alias as keys
                and a list of scraped data per alias as values.

        unique: bool, optional, defaults to True for non grouped results and
                False for grouped results.
            If set to True, will remove duplicates from returned result list.

        attr_fuzz_ratio: float in range [0, 1], optional, defaults to 1.0
            The fuzziness ratio threshold for matching html tag attributes.

        Returns:
        --------
        Pair of (similar, exact) results.
        See get_result_similar and get_result_exact methods.
        """

        soup = self._get_soup(url=url, html=html, request_args=request_args)
        args = dict(url=url, soup=soup, grouped=grouped, group_by_alias=group_by_alias,
                                        unique=unique, attr_fuzz_ratio=attr_fuzz_ratio)
        similar = self.get_result_similar(**args)
        exact = self.get_result_exact(**args)
        return similar, exact

    def remove_rules(self, rules):
        """
        Removes a list of learned rules from stack_list.

        Parameters:
        ----------
        rules : list
            A list of rules to be removed

        Returns:
        --------
        None
        """

        self.stack_list = [x for x in self.stack_list if x['stack_id'] not in rules]

    def keep_rules(self, rules):
        """
        Removes all other rules except the specified ones.

        Parameters:
        ----------
        rules : list
            A list of rules to keep in stack_list and removing the rest.

        Returns:
        --------
        None
        """

        self.stack_list = [x for x in self.stack_list if x['stack_id'] in rules]

    def set_rule_aliases(self, rule_aliases):
        """
        Sets the specified alias for each rule

        Parameters:
        ----------
        rule_aliases : dict
            A dictionary with keys of rule_id and values of alias

        Returns:
        --------
        None
        """

        id_to_stack = {stack['stack_id']: stack for stack in self.stack_list}
        for rule_id, alias in rule_aliases.items():
            id_to_stack[rule_id]['alias'] = alias

    def generate_python_code(self):
        # deprecated
        print('This function is deprecated. Please use save() and load() instead.')
