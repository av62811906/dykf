import datetime
import json
import time
import os
import random
import re

import cv2
import requests
import numpy as np
import selenium.common.exceptions
from PIL import Image
import base64
# import undetected_chromedriver.v2 as uc

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as Ec
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options

import db


class ChromeDriver(object):
    """

    webDriver基类

    """

    def __init__(self, url):
        # chrome 参数设定
        chrome_options = webdriver.ChromeOptions()
        # chrome_options.add_argument('--disable-gpu')
        # chrome_options.add_argument('--disable-dev-shm-usage')

        # 无窗体参数
        # chrome_options.add_argument("no-sandbox")
        # chrome_options.add_argument("--disable-extensions")
        # chrome_options.add_argument('headless')

        # driver参数设置
        # self.driver = uc.Chrome(use_subprocess=True)  # 无头driver
        self.driver = webdriver.Chrome(chrome_options=chrome_options)  # 普通driver
        self.url = url
        self.wait = WebDriverWait(self.driver, 10)

        # driver窗体大小
        self.driver.set_window_size(3440, 3000)

        # 图片验证码文件名
        self.slide_name = 'slide.jpg'
        self.background_name = 'background.jpg'

    def xpath_until(self, xpath, tp='click'):
        try:
            if tp == 'locate':
                return self.wait.until(
                    Ec.presence_of_element_located((By.XPATH, xpath))
                )
            else:
                return self.wait.until(
                    Ec.element_to_be_clickable((By.XPATH, xpath))
                )
        except selenium.common.exceptions.TimeoutException as e:
            print(f'[error] {datetime.datetime.now()} :{xpath}  没有找到')
            return None
        except selenium.common.exceptions.StaleElementReferenceException as e:
            time.sleep(3)
            print(f'[error] {datetime.datetime.now()} :{xpath}  出现StaleElementReferenceException')

    def element_click(self, element):
        try:
            element.click()
        except selenium.common.exceptions.ElementClickInterceptedException as e:
            print(e)
        except AttributeError as e:
            print(f"[error] {datetime.datetime.now()} :元素没有找到，不可点击")
        except selenium.common.exceptions.StaleElementReferenceException as e:
            time.sleep(3)
            print(f'[error] {datetime.datetime.now()} :click出现StaleElementReferenceException')
        except selenium.common.exceptions.ElementNotInteractableException as e:
            time.sleep(3)
            print(f'[error] {datetime.datetime.now()} :click出现ElementNotInteractableException')

    def window_switch(self, n):
        try:
            tab = self.driver.window_handles
            print(f'[info] {datetime.datetime.now()} :切换至选项卡{n}: {tab[n]}')
            self.driver.switch_to.window(tab[n])
        except Exception as e:
            print(f"[error] {datetime.datetime.now()} :选项卡切换失败，{e}")

    def retry(self, reason, func):
        try:
            print(f'[warning] {datetime.datetime.now()} : {reason}')
            func()
        except Exception as e:
            print(f'[error] {datetime.datetime.now()} : 重置错误')

    def quit(self):
        self.driver.close()

    def verification(self):
        """
        获取验证码图片,并识别和滑动
        :return:
        """

        def _save_img(url, filename):
            proxies = {
                'http': None,
                'https': None,
            }
            response = requests.get(url, verify=False, proxies=proxies)
            with open(filename, 'wb') as f:
                f.write(response.content)

        def _get_slide_locus(distance):
            distance += 8
            v = 0
            m = 0.3
            # 保存0.3内的位移
            tracks = []
            current = 0
            mid = distance * 4 / 5
            while current <= distance:
                if current < mid:
                    a = 2
                else:
                    a = -3
                v0 = v
                s = v0 * m + 0.5 * a * (m ** 2)
                current += s
                tracks.append(round(s))
                v = v0 + a * m
            return tracks

        def _slide_verification(driver, slide_element, distance):
            print(f'[info] {datetime.datetime.now()} :调整分辨率后滑动距离为 {distance}')
            # 根据滑动的距离生成滑动轨迹
            locus = _get_slide_locus(distance)

            print(f'[info] {datetime.datetime.now()} :生成的滑动轨迹为:{locus},轨迹的距离之和为{distance}')

            # 按下鼠标左键
            ActionChains(driver).click_and_hold(slide_element).perform()

            time.sleep(0.5)

            # 遍历轨迹进行滑动
            for loc in locus:
                time.sleep(0.01)
                ActionChains(driver).move_by_offset(loc, random.randint(-5, 5)).perform()
                ActionChains(driver).context_click(slide_element)

            # 释放鼠标
            ActionChains(driver).release(on_element=slide_element).perform()

        # 获取图片
        bg_img = self.xpath_until('//*[@id="captcha-verify-image"]', tp='locate')
        slide_img = self.xpath_until('//*[@id="captcha-verify-image"]/following-sibling::img[1]', tp='locate')

        # 获取图片地址
        bg_img_url = bg_img.get_attribute('src')
        slide_img_url = slide_img.get_attribute('src')

        # 保存图片
        _save_img(bg_img_url, self.background_name)
        _save_img(slide_img_url, self.slide_name)

        # 获取滑动距离
        distance = self.get_distance()

        # 获取网页图真实大小，和下载图片大小
        img_size = bg_img.size  # {'height': 212, 'width': 340}
        img_shape = cv2.imread(self.background_name).shape[1::-1]
        distance = distance / img_shape[0] * img_size['width'] - 12
        print(f'[info] {datetime.datetime.now()} :图片尺寸为{img_size}')
        print(f'[info] {datetime.datetime.now()} :图片分辨率为{img_shape}')

        # 获取滑块对象
        slide_block = self.xpath_until('//*[@id="secsdk-captcha-drag-wrapper"]/div[2]', tp='locate')

        # 滑动
        _slide_verification(driver=self.driver, slide_element=slide_block, distance=distance)

        # 校验验证是否通过
        try:
            time.sleep(3)
            self.driver.find_element(by=By.XPATH, value='//div[@class="captcha_verify_container style__CaptchaWrapper-sc-1gpeoge-0 zGYIR"]')
            print(f'[info] {datetime.datetime.now()} :校验失败，准备重新校验')
            time.sleep(3)
            self.verification()
        except:
            print(f'[info] {datetime.datetime.now()} :校验成功')

    def get_distance(self):
        """
        获取应该滑动的距离
        :return:
        """

        def _show(name):
            """展示圈出来的位置"""
            cv2.imshow('Show', name)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

        def _tran_canny(image):
            """消除噪声"""
            image = cv2.GaussianBlur(image, (3, 3), 0)
            return cv2.Canny(image, 50, 150)

        # 灰度模式
        image = cv2.imread(self.slide_name, 0)
        template = cv2.imread(self.background_name, 0)

        # 最佳匹配
        res = cv2.matchTemplate(_tran_canny(image), _tran_canny(template), cv2.TM_CCOEFF_NORMED)
        # 最小值，最大值，并得到最小值, 最大值的索引
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

        top_left = max_loc[0]  # 横坐标
        # 展示圈出来的区域
        x, y = max_loc  # 获取x,y位置坐标

        w, h = image.shape[::-1]  # 宽高
        cv2.rectangle(template, (x, y), (x + w, y + h), (7, 249, 151), 2)
        # _show(template)
        print(f'[info] {datetime.datetime.now()} :opencv计算滑动距离为{top_left}')
        return top_left

    def get_cookies(self, mail):
        with open(f'{mail}.txt', 'r', encoding='utf8') as f:
            list_cookies = json.loads(f.read())

        for cookie in list_cookies:
            cookie_dict = cookie
            print(f'[info] {datetime.datetime.now()} :加载cookie{cookie_dict["name"]}成功')
            self.driver.add_cookie(cookie_dict)


class Login(ChromeDriver):
    """

    登录

    使用说明：

    **********************************************************


    **********************************************************

    完成后会自动保存该账号的cookie，并生成txt文档



    """

    def __init__(self, url, mail, password):

        super().__init__(url)

        self.mail = mail
        self.password = password

    def login(self):
        """
        登录方法
        :param mail:
        :param password:
        :return:
        """

        # 请求网址
        self.driver.get(self.url)

        # switch_login切换
        time.sleep(1)
        switch_login = self.xpath_until(xpath='//*[@id="sdk-login-box"]/section/div[1]', tp='locate')
        switch_login.click()

        # 切换至邮箱登录
        mail_login = self.xpath_until('//*[@id="sdk-login-box"]/section/div[3]/div[1]')
        mail_login.click()

        # 输入账号密码
        mail_input = self.xpath_until('//*[@id="sdk-login-box"]/section/div[4]/div[1]/div[2]/div/input')
        password_input = self.xpath_until('//*[@id="sdk-login-box"]/section/div[4]/div[2]/div/div/input')
        mail_input.send_keys(self.mail)
        password_input.send_keys(self.password)

        # 点击登录
        submit = self.xpath_until('//*[@id="sdk-login-box"]/section/div[7]/button')
        submit.click()

        # 识别验证码
        self.verification()

        # 校验是否登录成功, 登录成功则获取cookie
        try:
            time.sleep(3)
            self.driver.find_element(by=By.XPATH, value='//*[@id="captcha-verify-image"]')
            print(f'[info] {datetime.datetime.now()} :账号{self.mail}登录失败')
            time.sleep(1)
            self.verification()
        except selenium.common.exceptions.NoSuchElementException:
            print(f'[info] {datetime.datetime.now()} :账号{self.mail}登录成功')

            # 登录成功后，获取cookie
            cookie = self.driver.get_cookies()
            jsonCookies = json.dumps(cookie)  # 转换成字符串保存
            with open(f'{self.mail}.txt', 'w') as f:
                f.write(jsonCookies)
            print(f'[info] {datetime.datetime.now()} :账号{self.mail}的cookie保存成功')
            self.driver.close()


class Glance(ChromeDriver):
    """

    浏览类

    使用说明：

    *******************************************************************************************

    *******************************************************************************************

    找出所有品退订单


    """

    def __init__(self, url, mail):
        super(Glance, self).__init__(url)
        self.mail = mail
        self.stores = self.glance_all_store()

    def glance_all_store(self):
        """
        查看所有店铺
        :return:
        """

        # 加载该账号的cookie
        self.driver.get(self.url)
        self.get_cookies(self.mail)
        self.driver.get(self.url)

        stores, _ = self._all_store(is_db=1)

        return stores

    def _all_store(self, is_db=0):

        # 获取所有店铺的链接
        self.xpath_until('//div[@class="index_wrapper__1CSI6"]', 'locate')
        print(f'[info] {datetime.datetime.now()} :店铺页面加载完成')
        stores = self.driver.find_elements(by=By.XPATH, value='//div[text()="进入店铺"]')
        print(f'[info] {datetime.datetime.now()} :获取该账号下所有店铺，共{len(stores)}个')

        # 获取所有店铺名
        store_names = self.driver.find_elements(by=By.XPATH, value='//div[@class="style_title__3cBdT"]')
        store_names = [x.text for x in store_names]

        if is_db:
            # 写入数据库
            db.insert_shop(store_names, self.mail)
            print(f'[info] {datetime.datetime.now()} :获取该账号下所有店铺写入数据完成, {str(store_names)[: 100]}  ...  ')

        return stores, store_names

    def _clean(self):
        xpath = '//*[contains(text(),"下一步") or contains(text(),"知道了") or contains(text(),"立即使用") or contains(text(),"退出引导") or text()="完成" or @class="ant-modal-close"]'

        while True:
            dialogs = self.driver.find_elements(by=By.XPATH, value=xpath)
            dialogs = self.driver.find_elements(by=By.XPATH, value=xpath)
            print(f'[info] {datetime.datetime.now()} :dialogs共{len(dialogs)}个')
            if not dialogs:
                time.sleep(10)
                if len(el := self.driver.find_elements(by=By.XPATH, value=xpath)) == 0:
                    print(f'[info] {datetime.datetime.now()} :清理页面完成')
                    break
            for dialog in dialogs:
                try:
                    print(f'[info] {datetime.datetime.now()} :dialog:{dialog.text}')
                    self.element_click(dialog)
                except selenium.common.exceptions.StaleElementReferenceException:
                    continue
                break
            time.sleep(1)

    def _new_edition(self):
        """
        进入新版
        :return:
        """

        new_edition = self.xpath_until('//span[text()="体验新版"]')
        self.element_click(new_edition)

    def _quality_refund(self):
        """
        进入品质退款页面
        :return:
        """
        # 点击店铺
        shop = self.xpath_until('//span[text()="店铺"]')
        self.element_click(shop)
        # 点击申诉中心d
        appeal_center = self.xpath_until('//span[text()="申诉中心"]')
        self.element_click(appeal_center)
        self._clean()
        # 点击体验分
        taikenbun = self.xpath_until('//div[text()="体验分-品质退货率申诉"]')
        self.element_click(taikenbun)
        # 查看是否有数据
        time.sleep(5)
        is_data = self.xpath_until('//div[text()="暂无数据"]', 'locate')

        print(f'[info] {datetime.datetime.now()} :{"找到品质退款" if not is_data else "无品质退款"}')

        return not is_data

    def _quality_refund_result(self):
        """
        查找品质退款结果并更新数据库
        :return:
        """

        result_lst = ['审核中', '申诉成功', '申诉失败', '补充申诉超时', '超时未申诉', '驳回待补充']

        for result in result_lst:
            self.element_click(self.xpath_until(f'//div[text()="{result}"]'))
            time.sleep(1)

            orders = self.driver.find_elements(by=By.XPATH, value='//div[@class="index_targetNumber__124JF"]')

            for order in orders:
                order = order.text
                rs = db.update_quality_refund_result(result, order)

        self.element_click(self.xpath_until(f'//div[text()="待申诉"]'))
        time.sleep(1)

        print(f'[info] {datetime.datetime.now()} :品退结果更新完成')

    def glance_order(self):
        """
        浏览订单
        :return:
        """

        def _clean():
            xpath = '//*[contains(text(),"下一步") or contains(text(),"知道了") or contains(text(),"立即使用") or contains(text(),"退出引导") or contains(text(), "完成")]'
            dialogs = self.driver.find_elements(by=By.XPATH, value=xpath)
            print(f'[info] {datetime.datetime.now()} :dialogs共{len(dialogs)}个')
            if dialogs:
                print(f'[info] {datetime.datetime.now()} :dialogs:{dialogs[0].text}')
            for dialog in dialogs:
                if dialog.text:
                    self.element_click(dialog)
            # 检查是否清理完毕
            # 检查方式：1.多次循环，看是否还有待清理的btn，2.循环通过后点击订单管理，看是否可点击
            check = self.xpath_until('//div[@class="secondMenuItem W-9UO1D++gF8RKxppWTmcg=="]/span[contains(text(),"订单管理")]', 'click')
            try:
                time.sleep(1)
                check.click()
                time.sleep(1)
                if len(el := self.driver.find_elements(by=By.XPATH, value=xpath)) != 0:
                    if len(el) == 1 and el[0].text == '':
                        pass
                    else:
                        self.retry(reason='清理失败，准备重新清洗', func=_clean)
                print(f'[info] {datetime.datetime.now()} :清理页面完成')
            except Exception as e:
                self.retry(reason='清理失败，准备重新清洗', func=_clean)

        def _find_pages():
            time.sleep(3)
            total = self.xpath_until('//li[@class="auxo-pagination-total-text"]/span', 'locate')
            if total:
                print(f'[info] {datetime.datetime.now()} :订单共有{total.text}条')
                total = re.search('\d+', total.text)
            if total:
                pages = int(total.group()) // 10 + 1
            else:
                self.driver.refresh()
                pages = _find_pages()
            print(f'[info] {datetime.datetime.now()} :订单共有{pages}页')
            return pages

        def _find_order():
            # 等待加载
            self.xpath_until('//div[@class="table_leftItem__4u2dX"]', 'click')
            # 获取所有聊天按钮
            orders = self.driver.find_elements(by=By.XPATH, value='//div[@class="table_leftItem__4u2dX"]')
            for order in orders:
                self.element_click(order)
                time.sleep(1)
                # 切换选项卡
                self.window_switch(1)
                # 关闭通知页面
                if not self.xpath_until('//a[@class="rnGBXsdi_B__2iceNrgg"]', 'click'):
                    alert = self.xpath_until('//div[@class="XPCbCjcIiCw0bzOFwSsX"]/img')
                    self.element_click(alert)
                # 检查是否有物流
                is_logistic = self.driver.find_elements(by=By.XPATH, value='//*[text()="物流信息"]')
                if is_logistic:
                    # 点击查看物流信息按钮
                    logistic = self.xpath_until('//div[@class="iozkO8OzVgI_Ye21uyg_"]/div[1]')
                    self.element_click(logistic)
                    # 查看是否出现验证码,并通过校验
                    if not self.xpath_until('//*[text()="运单号"]', 'locate'):
                        is_verify = self.xpath_until('//*[@id="fxg_risk_captcha_container"]/div')
                        try:
                            is_verify.click()
                            print(f'[info] {datetime.datetime.now()} :出现验证码，开始进行验证码识别')
                            self.verification()
                        except:
                            print(f'[info] {datetime.datetime.now()} :无验证码，继续执行')
                    print(f'[info] {datetime.datetime.now()} :获取物流信息')
                else:
                    print(f'[info] {datetime.datetime.now()} :无物流信息，继续执行')
                self.driver.close()
                self.window_switch(0)

        def _store_switch():
            """
            切换店铺
            :return:
            """
            # self.driver.save_screenshot(f'error.png')
            store_name = self.xpath_until('//div[@class="index_userName__16Isl"]', 'locate')
            self.element_click(store_name)

            logout = self.xpath_until('//div[text()="切换店铺"]')
            self.element_click(logout)

        def _img_concat(order_no):
            """
            图片拼接
            :return:
            """

            # 找到该订单号下所有图片
            dirs = os.listdir()
            cp = re.compile(f'^back_ato{order_no}-(.*?)\.png$')
            ato_dirs = [x for x in dirs if cp.match(x)]

            # 图片拼接
            for i, v in enumerate(ato_dirs):
                if i == 0:
                    img = Image.open(v)
                    img_array = np.array(img)
                if i > 0:
                    img_array2 = np.array(Image.open(v))
                    img_array = np.concatenate((img_array, img_array2), axis=0)
                    img = Image.fromarray(img_array)

            # 保存图片
            img.save(f'back_ato{order_no}.png')

            # 删除单个文件
            cp = re.compile(f'^back(.*?){order_no}-(.*?)\.png$')
            del_dirs = [x for x in dirs if cp.match(x)]
            for i in del_dirs:
                if os.path.exists(i):
                    os.remove(i)

        def _quality_refund_detail():
            """
            查看品质退款详细信息
            :return:
            """
            datas = self.driver.find_elements(by=By.XPATH, value='//div[@class="index_targetNumber__124JF"]')
            shop_belong = self.xpath_until('//div[@class="index_userName__16Isl"]', 'locate').text
            print(f'[info] {datetime.datetime.now()} :{shop_belong}品质退款共{len(datas)}个')
            for i, data in enumerate(datas):
                print(f'[info] {datetime.datetime.now()} :开始处理第{i + 1}个')
                self.element_click(data)
                self.window_switch(1)
                self._clean()

                # 获取数据
                account_belong = self.mail
                # shop_belong = self.xpath_until('//div[@class="index_userName__16Isl"]', 'locate').text
                order_no = self.xpath_until('//div[text()="售后编号"]/following-sibling::div[1]', 'locate').text
                illegal_type = ''
                stat = '待申诉'
                remain_time = ''
                refund_type = self.xpath_until('//div[text()="售后类型"]/following-sibling::div[1]', 'locate').text
                refund_reason = self.xpath_until('//div[text()="售后原因"]/following-sibling::div[1]', 'locate').text
                amount = self.xpath_until('//div[text()="申请金额"]/following-sibling::div[1]', 'locate').text
                trade_count = self.xpath_until('//div[text()="申请件数"]/following-sibling::div[1]', 'locate').text
                apply_time = self.xpath_until('//div[text()="申请时间"]/following-sibling::div[1]', 'locate').text
                consumer, phone = self.xpath_until('//div[text()="收货信息"]/following-sibling::div[1]', 'locate').text.split('\n')
                # phone = consumer
                product = self.xpath_until('//div[@class="index_ellipsis__29MP5 undefined"]', 'locate').text

                # 获取截图
                logistic_info = _get_logistic_info(order_no)
                chat_info = _get_chat_info(order_no)

                # 写入数据库
                db.insert_quality_refund(
                    account_belong=account_belong,
                    shop_belong=shop_belong,
                    order_no=order_no,
                    illegal_type=illegal_type,
                    stat=stat,
                    remain_time=remain_time,
                    refund_type=refund_type,
                    refund_reason=refund_reason,
                    amount=amount,
                    trade_count=trade_count,
                    apply_time=apply_time,
                    consumer=consumer,
                    phone=phone,
                    logistic_info=logistic_info,
                    chat_info=chat_info,
                    product=product,
                )
                print(f'[info] {datetime.datetime.now()} :{i + 1}个写入数据库完成')

                self.driver.close()
                self.window_switch(0)
                print(f'[info] {datetime.datetime.now()} :{i + 1}个处理完成')
                pass

        def _get_chat_info(order_no, height=10000):
            """
            获取聊天信息
            :return:
            """

            chat = self.xpath_until('//div[@class="style_box__3-8xW style_contract__CfLGW"]')
            self.driver.execute_script("arguments[0].click();", chat)
            time.sleep(2)
            self.window_switch(2)
            time.sleep(5)
            self.driver.set_window_size(self.driver.get_window_size().get("width"), height)
            time.sleep(5)
            b64 = _screenshot(height=height, order_no=order_no)

            # 转为base64
            f = open(f'img{order_no}.png', 'rb')
            b64 = base64.b64encode(f.read())
            f.close()

            # 删除文件
            os.remove(f'img{order_no}.png')

            self.driver.close()
            self.window_switch(1)

            return bytes.decode(b64)

        def _get_logistic_info(order_no):
            """
            获取物流信息
            :return:
            """

            tp_cns = {'退货物流': 'tuihuo',
                      '换货物流': 'huanhuo',
                      '订单物流': 'dingdan',
                      '测试测试': 'ceshiceshi'}

            for tp_cn in tp_cns.keys():
                try:
                    el = self.driver.find_element(by=By.XPATH, value=f'//div[text()="{tp_cn}"]')
                except:
                    continue

                print(f'[info] {datetime.datetime.now()} :找到{tp_cn}按钮')
                el.click()
                # 显示所有截图讯息
                _logistic_info_display_all()

                _screenshot_v2('//div[@class="auxo-tabs auxo-tabs-top auxo-tabs-large"]', order_no, tp=tp_cns.get(tp_cn))

            _img_concat(order_no)

            # 转为base64
            f = open(f'back_ato{order_no}.png', 'rb')
            b64 = base64.b64encode(f.read())
            f.close()

            # 删除文件
            # os.remove(f'back_ato{order_no}.png')

            return bytes.decode(b64)

        def _logistic_info_display_all():
            """
            拉大物流截图,获取其全部信息
            :return:
            """

            logis = self.driver.find_elements(by=By.XPATH, value='//div[@class="style_trace-scroll-view__2lpYR"]')

            for logi in logis:
                self.driver.execute_script("arguments[0].setAttribute(arguments[1],arguments[2])", logi, 'class', '')
                time.sleep(1)
            print(f'[info] {datetime.datetime.now()} :拉伸物流元素完成')

        def _screenshot(width=0, height=0, order_no='0'):
            """
            截图
            :return:
            """

            driver = self.driver

            # 取出页面的宽度和高度
            page_width = width if width else driver.execute_script("return document.body.scrollWidth")
            page_height = height if height else driver.execute_script("return document.body.scrollHeight")

            # 直接开启设备模拟
            driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride',
                                   {'mobile': False, 'width': page_width, 'height': page_height, 'deviceScaleFactor': 1})

            # 执行截图
            res = driver.execute_cdp_cmd('Page.captureScreenshot', {'fromSurface': True})

            # 返回的base64内容写入PNG文件
            with open(f'img{order_no}.png', 'wb') as f:
                img = base64.b64decode(res['data'])
                f.write(img)

            # 等待截图完成
            time.sleep(5)

            # 关闭设备模拟
            driver.execute_cdp_cmd('Emulation.clearDeviceMetricsOverride', {})
            print(f'[info] {datetime.datetime.now()} :screenshot截图完成')

            return res['data']

        def _screenshot_v2(el, order_no, tp='dingdan'):
            """
            截图方式2
            :return:
            """

            driver = self.driver

            # driver窗体大小
            self.driver.set_window_size(3440, 3000)

            # 定位元素
            block = self.xpath_until(el, 'locate')

            # 获取元素坐标
            top = block.location['y']

            # 滚动条下拉
            js = f"var q=document.documentElement.scrollTop={top - 200}"
            driver.execute_script(js)
            time.sleep(1)

            # 获取元素坐标
            left = block.location['x']
            top = 200
            right = left + block.size['width']
            bottom = top + block.size['height']
            print(block.size)

            # 截取背景图
            driver.save_screenshot(f'back{order_no}-{tp}.png')

            # 从背景中截取元素
            pic = Image.open(f'back{order_no}-{tp}.png')
            pic = pic.crop((left, top, right, bottom))
            pic.save(f'back_ato{order_no}-{tp}.png')

            # 回顶部
            js = "var q=document.documentElement.scrollTop=0"
            driver.execute_script(js)
            time.sleep(1)

            print(f'[info] {datetime.datetime.now()} :screenshot_v2截图完成')

        for i in range(0, len(self.stores)):
            store, store_name = self._all_store()
            store = store[i]
            store_name = store_name[i]
            if db.find_shop_is_alive(store_name):  # 店铺存活则进入爬取逻辑
                # 浏览当前店铺
                print(f'[info] {datetime.datetime.now()} :{store_name}开始浏览:')
                self.element_click(store)
                # 清理页面
                self._clean()
                # 进入新版
                self._new_edition()
                # 清理新版页面
                self._clean()
                # 进入品质退款页面
                is_data = self._quality_refund()
                # 查看品退结果
                self._quality_refund_result()
                if is_data:
                    # 有品质退款,查看详细页面
                    _quality_refund_detail()
                # 切换店铺
                print(f'[info] {datetime.datetime.now()} :{store_name}浏览完成:')
                _store_switch()

                time.sleep(1)


class GlanceOld(ChromeDriver):

    def __init__(self, url, mail):
        super(GlanceOld, self).__init__(url)
        self.mail = mail

    def glance_homepage(self):
        """
        主页
        :return:
        """

        def _get_cookies():
            with open(f'{self.mail}.txt', 'r', encoding='utf8') as f:
                list_cookies = json.loads(f.read())

            for cookie in list_cookies:
                cookie_dict = cookie
                print(f'[info] {datetime.datetime.now()} :加载cookie{cookie_dict["name"]}成功')
                self.driver.add_cookie(cookie_dict)

        def _clean():
            # 关闭通知
            msg_close = self.xpath_until("//button[@class='ant-modal-close']")
            self.element_click(msg_close)

            # 关闭引导
            guide_close = self.xpath_until('//div[contains(text(), "退出引导")]')
            self.element_click(guide_close)

            # 关闭新功能
            for i in range(7):
                new_close = self.xpath_until('//button[contains(text(), "知道了")]')
                self.element_click(new_close)

            # 验证清理是否完成
            check = self.xpath_until('//div[@class="firstMenu TQlJ1SUhlsocF8cfaX+mTA=="]//span[text()="首页"]')
            try:
                check.click()
                print(f'[info] {datetime.datetime.now()} :清理页面完成')
            except:
                self.retry(reason='清理失败，准备重新清洗', func=_clean)

        # 加载cookie并打开driver
        self.driver.get(self.url)
        _get_cookies()
        self.driver.get(self.url)

        # 清理页面弹窗
        _clean()

    def glance_order(self):
        """
        浏览订单管理页面
        :return:
        """
        # 点击订单管理
        order_management = self.xpath_until('//span[contains(text(), "订单管理")]')
        self.element_click(order_management)
        print(f'[info] {datetime.datetime.now()} :进入订单管理页面')

        # 找到所有订单
        page = self.xpath_until(
            '//div[@class="auxo-select auxo-select-sm auxo-pagination-options-size-changer auxo-select-single auxo-select-show-arrow"]',
            tp='locate')
        time.sleep(1)
        orders = self.driver.find_elements(by=By.XPATH, value='//a[@class="table_nickname__3m0Ja"]')
        print(f'[info] {datetime.datetime.now()} :找到本页所有订单, 个数{len(orders)}')

        # 点击该页的所有订单
        for order in orders:
            self.element_click(order)
            time.sleep(1)
            # 切换选项卡
            self.window_switch(1)
            # 关闭通知页面
            alert = self.xpath_until('//div[@class="XPCbCjcIiCw0bzOFwSsX"]/img')
            self.element_click(alert)
            # 点击查看物流信息按钮
            logistic = self.xpath_until('//div[@class="iozkO8OzVgI_Ye21uyg_"]/div[1]')
            self.element_click(logistic)
            # 查看是否出现验证码,并通过校验
            is_verify = self.xpath_until('//*[@id="fxg_risk_captcha_container"]/div')
            try:
                is_verify.click()
                print(f'[info] {datetime.datetime.now()} :出现验证码，开始进行验证码识别')
                self.verification()
            except:
                print(f'[info] {datetime.datetime.now()} :无验证码，继续执行')

            time.sleep(50000)


class Appeal(Glance):

    def __init__(self, url, data):
        self.data = data
        super(Appeal, self).__init__(url, data.get('email'))

    def _target_store(self):
        # 进入目标店铺

        # 找到目标店铺下标
        store_names = self.driver.find_elements(by=By.XPATH, value='//div[@class="style_title__3cBdT"]')
        store_names = [x.text for x in store_names]
        idx = store_names.index(self.data.get('shop_belong'))

        # 进入该店铺
        self.element_click(self.stores[idx])
        print(f'[info] {datetime.datetime.now()} :进入目标店铺, "{self.data.get("shop_belong")}"')

    def _appeal_button_click(self):
        """
        点击申诉按钮,并填写表格
        :return:
        """

        # 判断申诉类型
        # 如果类型为驳回待补充(未测试)
        if int(self.data.get('appeal_type')) == 1:
            self.element_click(self.xpath_until('//div[text()="驳回待补充"]'))

        # 找到该订单号的index
        order_numbers = self.driver.find_elements(by=By.XPATH, value='//div[@class="index_targetNumber__124JF"]')
        order_numbers = [x.text for x in order_numbers]
        idx = order_numbers.index(self.data.get('order_no'))

        # 点击申诉目标按钮
        btns = self.driver.find_elements(by=By.XPATH, value='//button/span[text()="申诉"]')
        self.element_click(btns[idx])
        print(f'[info] {datetime.datetime.now()} :进入目标店铺"{self.data.get("shop_belong")}"申诉页面')

        # 填写表格
        submit = self.xpath_until('//button/span[text()="提交"]')

        # 原因
        self.element_click(self.xpath_until('//input[@id="reason"]', 'locate'))
        options = self.driver.find_elements(by=By.XPATH, value='//div[@class="ant-select-item-option-content"]')
        self.element_click(options[self.data.get('appeal_reason')])

        # 理由
        self.xpath_until('//textarea[@id="appeal_cause"]', 'locate').send_keys(self.data.get('appeal_argument'))

        # 联系方式
        self.xpath_until('//input[@id="phone_num"]', 'locate').send_keys(self.data.get('stuff'))

        # 图片和视频上传
        paths = []
        for i in range(self._b64_2_file()):
            path = os.path.abspath('') + '/' + self.data.get('email') + f'appealpic{i}.jpg'
            paths.append(path)
            self.xpath_until('//input[@id="proof"]', 'locate').send_keys(path)
            time.sleep(5)
        for i in range(self._b64_2_file(tp='video')):
            path = os.path.abspath('') + '/' + self.data.get('email') + f'appealvideo{i}.jpg'
            paths.append(path)
            self.xpath_until('//input[@type="file" and @accept=".mp4"]', 'locate').send_keys(path)
            time.sleep(10)

        # 点击提交
        # self.element_click(submit)

        # 修改数据库中requireCrawl为1
        db.set_require_crawl_for_appeal(self.data.get('id'), 0)
        db.set_stat(self.data.get('order_no'), '已处理')

        # 删除本地图片
        for path in paths:
            os.remove(path)

        time.sleep(3)

        self.driver.quit()

    def _b64_2_file(self, tp='pic'):
        """
        将b64转为文件
        :return:
        """

        imgdata = self.data.get(tp, '').split(',')
        for i, img in enumerate(imgdata):
            img = base64.b64decode(img)
            file = open(self.data.get('email') + f'appeal{tp}{i}.{"jpg" if tp=="pic" else "mp4"}', 'wb')
            file.write(img)
            file.close()

        # return os.path.abspath('') + '\\' + self.data.get('email') + 'appeal.jpg'
        return len(imgdata)

    def appeal_handler(self):
        """
        处理申诉流程
        :return:
        """

        # 进入目标店铺
        self._target_store()
        # 清理
        self._clean()
        # 进入新版
        self._new_edition()
        # 进入品质退款页面
        self._quality_refund()
        # 点击申诉
        self._appeal_button_click()


if __name__ == '__main__':

    pass
