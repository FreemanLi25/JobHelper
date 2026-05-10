import random
import re
import socket
import threading
import time
import traceback
from queue import Empty, Queue
from typing import Iterable, Optional
from urllib.error import URLError
from urllib.request import urlopen

import customtkinter as ctk
from DrissionPage import ChromiumPage


# =========================
# 固定配置
# =========================

DEBUGGER_ADDRESS = "127.0.0.1:9222"
BOSS_HOME_URL = "https://www.zhipin.com/"


# Boss 直聘页面会不定期调整 class 名，因此这里尽量准备多套候选定位。
# DrissionPage 支持 css: 和 xpath: 两种常用定位方式。
SEARCH_INPUT_SELECTORS = [
    "css:input[name='query']",
    "css:input[placeholder*='职位']",
    "css:input[placeholder*='搜索']",
    "xpath://input[contains(@placeholder, '职位') or contains(@placeholder, '搜索')]",
]

SEARCH_BUTTON_SELECTORS = [
    "css:.search-btn",
    "css:button[type='submit']",
    "xpath://button[contains(., '搜索')]",
    "xpath://a[contains(., '搜索')]",
]

CITY_SELECTORS = [
    "css:.city-label",
    "css:.city-text",
    "css:.location-city",
    "xpath://span[contains(@class, 'city') and string-length(normalize-space(.)) > 0]",
    "xpath://a[contains(., '城市') or contains(., '全国')]",
]

JOB_CARD_SELECTORS = [
    "css:.job-card-box",
    "css:.job-card-wrapper",
    "css:.job-card-body",
    "css:.job-list-container .job-card-box",
    "css:.job-card-list .job-card-box",
    "css:.search-job-result .job-card-box",
    "css:.job-list-box li",
    "css:.job-card-left",
    "xpath://div[contains(@class, 'job-card-box') or contains(@class, 'job-card-wrapper') or contains(@class, 'job-card-body')]",
    "xpath://li[contains(@class, 'job-card') or contains(@class, 'job-list')]",
]

SALARY_SELECTORS = [
    "css:.salary-name",
    "css:.job-salary",
    "css:.salary",
    "css:.red",
    "xpath:.//*[contains(@class, 'salary') or contains(@class, 'red') or contains(@class, 'wage')]",
]

JOB_NAME_SELECTORS = [
    "css:.job-title",
    "css:.job-name",
    "css:.job-card-left .job-title",
    "css:.job-card-body .job-title",
    "css:.name",
    "xpath:.//*[contains(@class, 'job-name') or contains(@class, 'job-title') or contains(@class, 'name')]",
]

COMPANY_SELECTORS = [
    "css:.company-name",
    "css:.company-text",
    "css:.company-title",
    "css:.job-card-footer .name",
    "css:.job-card-footer span",
    "xpath:.//*[contains(@class, 'company') or contains(@class, 'brand') or contains(@class, 'firm')]",
]

COMMUNICATE_SELECTORS = [
    "xpath://button[contains(., '立即沟通') or contains(., '继续沟通') or contains(., '打招呼')]",
    "xpath://a[contains(., '立即沟通') or contains(., '继续沟通') or contains(., '打招呼')]",
    "xpath://span[contains(., '立即沟通') or contains(., '继续沟通') or contains(., '打招呼')]",
]

NEXT_PAGE_SELECTORS = [
    "css:.options-pages a.next",
    "css:.pagination .next",
    "xpath://a[contains(., '下一页') and not(contains(@class, 'disabled'))]",
    "xpath://button[contains(., '下一页') and not(@disabled)]",
    "xpath://button[contains(., '查看更多') and not(@disabled)]",
    "xpath://a[contains(., '查看更多') and not(contains(@class, 'disabled'))]",
]

CLOSE_POPUP_SELECTORS = [
    "css:.dialog-close",
    "css:.close",
    "css:.icon-close",
    "css:.boss-popup__close",
    "xpath://button[contains(., '取消') or contains(., '关闭') or contains(., '稍后')]",
    "xpath://i[contains(@class, 'close')]",
    "xpath://span[contains(@class, 'close')]",
]

STAY_ON_PAGE_SELECTORS = [
    "xpath://button[normalize-space()='留在此页']",
    "xpath://a[normalize-space()='留在此页']",
    "xpath://span[normalize-space()='留在此页']",
    "xpath://button[contains(., '留在此页')]",
    "xpath://a[contains(., '留在此页')]",
]

EXPERIENCE_OPTIONS = ["不限", "在校生", "应届生", "经验不限", "1年以内", "1-3年", "3-5年", "5-10年", "10年以上"]

EXPERIENCE_ALIASES = {
    "在校生": ["在校生", "在校"],
    "应届生": ["应届生", "应届", "在校/应届", "校招"],
    "经验不限": ["经验不限", "不限"],
}


def parse_salary_top_k(salary_text: str) -> Optional[int]:
    """解析 Boss 常见薪资文本，返回月薪上限 K。

    规则：
    1. 必须包含 K/k，排除 200-300/天、30/小时 等日薪/时薪。
    2. 支持 15-25K、15-25K·14薪、18K、18k-30k 等写法。
    3. 返回最高值，例如 15-25K·14薪 返回 25。
    """
    if not salary_text:
        return None

    text = normalize_boss_obfuscated_digits(salary_text).strip()
    lower_text = text.lower()

    if "k" not in lower_text:
        return None

    # 日薪、时薪、按次等不属于月薪 K，直接排除。
    if any(unit in text for unit in ["天", "日", "小时", "时", "/天", "/日", "/小时"]):
        return None

    # 优先处理区间写法：15-25K、18k-30k、20 至 35K。
    # 只取第一个 K 薪区间，避免把 “14薪” 里的 14 误判成薪资数字。
    range_match = re.search(
        r"(\d+(?:\.\d+)?)\s*[kK]?\s*[-~—–至到]\s*(\d+(?:\.\d+)?)\s*[kK]",
        text,
    )
    if range_match:
        return int(float(range_match.group(2)))

    single_match = re.search(r"(\d+(?:\.\d+)?)\s*[kK]", text)
    if single_match:
        return int(float(single_match.group(1)))

    return None


def normalize_boss_obfuscated_digits(text: str) -> str:
    """还原 Boss 页面常见的私有区数字字符。

    Boss 直聘部分页面会把薪资数字渲染成 Unicode 私有区字符：
    U+E031-U+E03A 分别对应 0-9。比如 “-K” 实际是 “15-25K”。
    """
    if not text:
        return ""

    trans = {ord(chr(0xE031 + digit)): str(digit) for digit in range(10)}
    return text.translate(trans)


def clean_job_name(job_name: str, salary_text: str = "") -> str:
    """清理卡片标题，避免职位名里混入薪资、经验、学历等多行信息。"""
    if not job_name:
        return "未识别职位名"

    normalized = normalize_boss_obfuscated_digits(job_name).strip()
    if salary_text:
        normalized_salary = normalize_boss_obfuscated_digits(salary_text).strip()
        normalized = normalized.replace(normalized_salary, "").strip()

    normalized = re.split(r"\d+(?:\.\d+)?\s*[kK]\b|\d+(?:\.\d+)?\s*[-~—–至到]\s*\d+(?:\.\d+)?\s*[kK]", normalized)[0]
    normalized = normalized.splitlines()[0].strip()
    return normalized or "未识别职位名"


def split_blocked_companies(text: str) -> list[str]:
    """按中文/英文分号切分公司黑名单关键词。"""
    if not text:
        return []
    return [item.strip().lower() for item in re.split(r"[；;]", text) if item.strip()]


def salary_meets_requirement(salary_text: str, min_salary_k: int) -> bool:
    """判断薪资是否满足设定下限。"""
    top_k = parse_salary_top_k(salary_text)
    return top_k is not None and top_k >= min_salary_k


class BossAutoGreeter:
    """后台自动化核心。

    所有浏览器操作都在工作线程中执行，GUI 线程只负责显示日志和响应按钮。
    """

    def __init__(self, log_func, stop_event: threading.Event):
        self.log = log_func
        self.stop_event = stop_event
        self.page: Optional[ChromiumPage] = None

    def connect_page(self) -> ChromiumPage:
        """固定接管 127.0.0.1:9222 的 Edge/Chromium 页面。"""
        self.log(f"正在连接浏览器调试端口：{DEBUGGER_ADDRESS}")
        browser_info = self.ensure_debugger_port_ready()
        self.log(f"检测到远程调试浏览器：{browser_info}")
        page = ChromiumPage(DEBUGGER_ADDRESS)
        self.page = page
        title = self.safe_get_title(page)
        self.log(f"浏览器连接成功，当前页面标题：{title or '未获取到标题'}")
        return page

    def ensure_debugger_port_ready(self) -> str:
        """先探测 9222 端口，避免 DrissionPage 在端口未开启时自动拉起 Chrome。"""
        host, port_text = DEBUGGER_ADDRESS.split(":", 1)
        port = int(port_text)

        try:
            with socket.create_connection((host, port), timeout=2):
                pass
        except OSError as exc:
            raise RuntimeError(
                "未检测到 127.0.0.1:9222 调试端口。请先运行 start_edge_debug.bat，"
                "并确认 Edge 已打开后再点击测试连接。"
            ) from exc

        try:
            with urlopen(f"http://{DEBUGGER_ADDRESS}/json/version", timeout=3) as response:
                body = response.read().decode("utf-8", errors="replace")
        except URLError as exc:
            raise RuntimeError("9222 端口已打开，但无法读取 /json/version，请确认这是 Edge/Chromium 调试端口。") from exc

        browser_match = re.search(r'"Browser"\s*:\s*"([^"]+)"', body)
        user_agent_match = re.search(r'"User-Agent"\s*:\s*"([^"]+)"', body)
        browser = browser_match.group(1) if browser_match else "未知浏览器"
        user_agent = user_agent_match.group(1) if user_agent_match else ""

        if "Edg/" not in user_agent and "Edge/" not in user_agent:
            self.log("警告：9222 端口当前不是 Edge User-Agent，可能是 Chrome 或其他 Chromium 浏览器。")

        return browser

    def test_connection(self) -> None:
        """仅测试连接，不执行任何业务操作。"""
        page = self.connect_page()
        self.log(f"测试完成：已成功接管 {DEBUGGER_ADDRESS}。")
        self.log(f"提示：请确认该浏览器已登录 Boss 直聘账号。当前 URL：{self.safe_get_url(page)}")

    def run(
        self,
        keyword: str,
        city: str,
        min_salary_k: int,
        max_count: int,
        experience_filter: str = "不限",
        blocked_companies: Optional[list[str]] = None,
    ) -> None:
        """执行完整自动海投流程。"""
        sent_count = 0
        blocked_companies = blocked_companies or []
        page = self.connect_page()

        self.log("开始执行任务。若页面要求登录、验证码或安全验证，请先在接管的 Edge 中手动处理。")
        experience_applied = self.navigate_and_search(page, keyword, city, experience_filter)
        if experience_filter and experience_filter != "不限":
            self.log(f"工作经验限制：{experience_filter}")
            if experience_applied:
                self.log("已检测到页面工作经验筛选生效，卡片侧仅做同义词宽松校验。")
        if blocked_companies:
            self.log(f"公司限制关键词：{'；'.join(blocked_companies)}")

        batch_index = 1
        empty_scroll_rounds = 0
        seen_job_keys = set()
        while not self.stop_event.is_set() and sent_count < max_count:
            self.log(f"开始遍历第 {batch_index} 批已加载职位卡片。")
            cards = self.wait_job_cards(page)

            if not cards:
                self.log("未识别到职位卡片，可能页面结构变化、未登录或搜索结果为空。")
                break

            processed_this_batch = 0
            for idx, card in enumerate(cards, start=1):
                if self.stop_event.is_set() or sent_count >= max_count:
                    break

                raw_salary_text = self.extract_text_from_child(card, SALARY_SELECTORS) or "未识别薪资"
                salary_text = normalize_boss_obfuscated_digits(raw_salary_text)
                job_name = clean_job_name(self.extract_text_from_child(card, JOB_NAME_SELECTORS), raw_salary_text)
                company_text = self.extract_company_text(card)
                card_text = normalize_boss_obfuscated_digits((getattr(card, "text", "") or "")).lower()
                job_key = f"{job_name}|{salary_text}"
                if job_key in seen_job_keys:
                    continue
                seen_job_keys.add(job_key)
                processed_this_batch += 1

                if not self.card_matches_experience(card, experience_filter, experience_applied):
                    self.log(f"[跳过] 第 {idx} 个职位：{job_name}，原因：工作经验不符合 {experience_filter}。")
                    continue

                blocked_keyword = self.find_blocked_company_keyword(company_text, card_text, blocked_companies)
                if blocked_keyword:
                    company_log = company_text or "未识别公司"
                    self.log(f"[跳过] 第 {idx} 个职位：{job_name}，公司：{company_log}，命中公司限制：{blocked_keyword}。")
                    continue

                top_k = parse_salary_top_k(raw_salary_text)
                salary_log_text = salary_text if salary_text == raw_salary_text else f"{raw_salary_text} -> {salary_text}"

                if top_k is None:
                    self.log(f"[跳过] 第 {idx} 个职位：{job_name}，薪资：{salary_log_text}，原因：非月薪 K 或无法解析。")
                    continue

                if top_k < min_salary_k:
                    self.log(f"[跳过] 第 {idx} 个职位：{job_name}，薪资：{salary_log_text}，薪资上限 {top_k}K < {min_salary_k}K。")
                    continue

                self.log(f"[符合] 第 {idx} 个职位：{job_name}，薪资：{salary_log_text}，准备点击立即沟通。")
                self.human_pause("点击前随机等待")
                self.random_scroll(page)

                if self.click_communicate(card, page):
                    sent_count += 1
                    self.log(f"[成功] 已沟通 {sent_count}/{max_count}：{job_name}")
                    self.close_or_leave_dialog(page)
                else:
                    self.log(f"[失败] 未能点击沟通按钮：{job_name}")

            if sent_count >= max_count:
                break

            self.log(f"本批新处理职位数：{processed_this_batch}，累计已见职位数：{len(seen_job_keys)}。")

            self.human_pause("加载更多职位前随机等待")
            if not self.scroll_load_more_jobs(page, seen_job_keys):
                empty_scroll_rounds += 1
                self.log(f"本次滚动未发现新职位，连续无新增次数：{empty_scroll_rounds}/3。")
            else:
                empty_scroll_rounds = 0

            if empty_scroll_rounds >= 3:
                self.log("连续多次滚动后未发现新职位，任务结束。")
                break

            batch_index += 1

        if self.stop_event.is_set():
            self.log(f"任务已被用户强制停止，已成功沟通 {sent_count} 个职位。")
        else:
            self.log(f"任务完成，累计成功沟通 {sent_count} 个职位。")

    def navigate_and_search(self, page: ChromiumPage, keyword: str, city: str, experience_filter: str = "不限") -> bool:
        """打开 Boss 首页，切换城市，并搜索目标岗位。"""
        current_url = self.safe_get_url(page)
        if "zhipin.com" not in current_url:
            self.log(f"当前不在 Boss 直聘，正在打开：{BOSS_HOME_URL}")
            page.get(BOSS_HOME_URL)
            self.wait_page_loaded_soft(page)

        self.try_choose_city(page, city)

        search_input = self.find_first(page, SEARCH_INPUT_SELECTORS, timeout=8)
        if not search_input:
            raise RuntimeError("未找到搜索框，请确认当前页面是否为 Boss 直聘搜索页或首页。")

        self.log(f"输入岗位关键词：{keyword}")
        try:
            search_input.clear()
        except Exception:
            pass
        search_input.input(keyword)

        if not self.click_search_button(page):
            self.log("未能直接点击搜索按钮，改用回车触发搜索。")
            search_input.input("\n")

        self.wait_page_loaded_soft(page)
        self.wait_job_cards(page)
        experience_applied = self.apply_experience_filter(page, experience_filter)
        if experience_filter and experience_filter != "不限":
            self.wait_page_loaded_soft(page)
            self.wait_job_cards(page)
        self.log("搜索结果已加载，进入职位遍历。")
        return experience_applied

    def apply_experience_filter(self, page: ChromiumPage, experience_filter: str) -> bool:
        """尽量点击 Boss 顶部工作经验筛选；失败时交给卡片侧过滤兜底。"""
        if not experience_filter or experience_filter == "不限":
            return False

        self.log(f"尝试选择工作经验：{experience_filter}")
        try:
            trigger = self.find_first(
                page,
                [
                    "xpath://button[contains(., '工作经验')]",
                    "xpath://a[contains(., '工作经验')]",
                    "xpath://span[contains(., '工作经验')]",
                    "xpath://div[contains(., '工作经验') and string-length(normalize-space(.)) < 20]",
                ],
                timeout=4,
            )
            if trigger:
                self.safe_click(trigger, "工作经验筛选")
                time.sleep(0.8)

            option = self.find_first(
                page,
                [
                    f"xpath://li[normalize-space()='{experience_filter}']",
                    f"xpath://a[normalize-space()='{experience_filter}']",
                    f"xpath://span[normalize-space()='{experience_filter}']",
                    f"xpath://div[normalize-space()='{experience_filter}']",
                ],
                timeout=4,
            )
            if option:
                self.safe_click(option, f"工作经验选项 {experience_filter}")
                self.log(f"已选择工作经验：{experience_filter}")
                time.sleep(1.5)
                return True
            else:
                self.log("未找到工作经验下拉选项，将使用卡片文本进行经验过滤。")
        except Exception as exc:
            self.log(f"选择工作经验失败，将使用卡片文本进行经验过滤：{exc}")
        return False

    def try_choose_city(self, page: ChromiumPage, city: str) -> None:
        """尽量切换城市；若页面结构不匹配，记录日志并继续搜索。"""
        self.log(f"尝试切换工作地点：{city}")
        try:
            city_entry = self.find_first(page, CITY_SELECTORS, timeout=5)
            if city_entry:
                self.safe_click(city_entry, "城市入口")
                time.sleep(1)

            city_option = self.find_first(
                page,
                [
                    f"xpath://a[normalize-space()='{city}']",
                    f"xpath://span[normalize-space()='{city}']",
                    f"xpath://li[contains(normalize-space(), '{city}')]",
                ],
                timeout=5,
            )
            if city_option:
                self.safe_click(city_option, "城市选项")
                self.log(f"城市已切换为：{city}")
                self.wait_page_loaded_soft(page)
            else:
                self.log("未找到城市选项，继续使用页面当前城市。")
        except Exception as exc:
            self.log(f"城市切换失败，继续使用当前城市。原因：{exc}")

    def wait_job_cards(self, page: ChromiumPage):
        """显式等待职位卡片加载。"""
        deadline = time.time() + 12
        last_cards = []
        while time.time() < deadline and not self.stop_event.is_set():
            cards = self.find_all_first_match(page, JOB_CARD_SELECTORS)
            if cards:
                return cards
            time.sleep(0.5)
        return last_cards

    def click_communicate(self, card, page: ChromiumPage) -> bool:
        """点击卡片内或详情页中的“立即沟通”。"""
        try:
            # 部分页面需要先点卡片，再在详情区域点击立即沟通。
            try:
                self.safe_click(card, "职位卡片")
                time.sleep(1.2)
            except Exception:
                pass

            button = self.find_first(card, COMMUNICATE_SELECTORS, timeout=2)
            if not button:
                button = self.find_first(page, COMMUNICATE_SELECTORS, timeout=4)

            if not button:
                return False

            self.safe_click(button, "立即沟通按钮")
            time.sleep(1.8)
            return True
        except Exception as exc:
            self.log(f"点击立即沟通异常：{exc}")
            return False

    def close_or_leave_dialog(self, page: ChromiumPage) -> None:
        """处理聊天窗口、发送简历、确认弹窗等拦截，尽量回到列表页继续。"""
        try:
            # Boss 发出消息后常弹出 “已向BOSS发送消息”，必须点“留在此页”。
            # 点“继续沟通”会进入聊天页，点右上角关闭有时也会让页面状态卡住。
            stay_btn = self.find_first(page, STAY_ON_PAGE_SELECTORS, timeout=3)
            if stay_btn:
                self.safe_click(stay_btn, "留在此页按钮")
                self.log("已点击“留在此页”，继续处理职位列表。")
                time.sleep(0.8)
                return

            # 先尝试点击各种关闭/取消按钮。
            for selector in CLOSE_POPUP_SELECTORS:
                try:
                    close_btn = page.ele(selector, timeout=1)
                    if close_btn:
                        self.safe_click(close_btn, "弹窗关闭按钮")
                        self.log("已自动关闭弹窗或对话框。")
                        time.sleep(0.8)
                        return
                except Exception:
                    continue

            # 如果点击后进入了聊天或详情页面，使用后退回到搜索列表。
            url = self.safe_get_url(page)
            if any(key in url for key in ["/chat", "/geek/chat", "/job_detail"]):
                page.back()
                self.log("检测到页面跳转，已执行后退回到列表。")
                self.wait_page_loaded_soft(page)
        except Exception as exc:
            self.log(f"弹窗处理异常，继续执行后续任务：{exc}")

    def scroll_load_more_jobs(self, page: ChromiumPage, seen_job_keys: set[str]) -> bool:
        """新版 Boss 搜索结果使用无限滚动，不点击分页，只滚动加载更多职位。"""
        try:
            before_count = len(self.find_all_first_match(page, JOB_CARD_SELECTORS))
            distance = random.randint(900, 1600)
            js = f"""
            const containers = Array.from(document.querySelectorAll('*')).filter((el) => {{
                const style = window.getComputedStyle(el);
                return /(auto|scroll)/.test(style.overflowY)
                    && el.scrollHeight > el.clientHeight + 100
                    && el.getBoundingClientRect().height > 200;
            }});
            const target = containers.sort((a, b) => b.scrollHeight - a.scrollHeight)[0];
            if (target) {{
                target.scrollBy(0, {distance});
            }} else {{
                window.scrollBy(0, {distance});
            }}
            return true;
            """
            page.run_js(js)
            self.log(f"已向下滚动加载更多职位：{distance}px。")
            time.sleep(random.uniform(2.0, 3.5))
            after_count = len(self.find_all_first_match(page, JOB_CARD_SELECTORS))
            if after_count > before_count:
                self.log(f"检测到职位列表增加：{before_count} -> {after_count}。")
                return True

            # 虚拟列表可能复用 DOM 节点，数量不变但内容已刷新；检查是否出现新的职位 key。
            for card in self.find_all_first_match(page, JOB_CARD_SELECTORS):
                raw_salary_text = self.extract_text_from_child(card, SALARY_SELECTORS) or "未识别薪资"
                salary_text = normalize_boss_obfuscated_digits(raw_salary_text)
                job_name = clean_job_name(self.extract_text_from_child(card, JOB_NAME_SELECTORS), raw_salary_text)
                if f"{job_name}|{salary_text}" not in seen_job_keys:
                    self.log("职位卡片数量未增加，但检测到虚拟列表刷新出新职位。")
                    return True
            return False
        except Exception as exc:
            self.log(f"滚动加载更多失败：{exc}")
            return False

    def human_pause(self, reason: str) -> None:
        """反风控随机等待，所有点击和翻页前必须调用。"""
        seconds = random.uniform(3.5, 7.8)
        self.log(f"{reason}：{seconds:.1f} 秒。")
        end = time.time() + seconds
        while time.time() < end:
            if self.stop_event.is_set():
                return
            time.sleep(0.2)

    def random_scroll(self, page: ChromiumPage) -> None:
        """模拟随机向下滚动。"""
        try:
            distance = random.randint(180, 620)
            page.run_js(f"window.scrollBy(0, {distance});")
            self.log(f"已模拟随机向下滚动：{distance}px。")
            time.sleep(random.uniform(0.4, 1.0))
        except Exception as exc:
            self.log(f"随机滚动失败，继续执行：{exc}")

    @staticmethod
    def find_first(scope, selectors: Iterable[str], timeout: float = 3):
        """按候选选择器返回第一个命中的元素。"""
        for selector in selectors:
            try:
                ele = scope.ele(selector, timeout=timeout)
                if ele:
                    return ele
            except Exception:
                continue
        return None

    @staticmethod
    def find_all_first_match(scope, selectors: Iterable[str]):
        """按候选选择器返回第一组非空元素列表。"""
        for selector in selectors:
            try:
                items = scope.eles(selector)
                if items:
                    return items
            except Exception:
                continue
        return []

    def click_search_button(self, page: ChromiumPage) -> bool:
        """点击当前页面可见的搜索按钮，避开自动补全浮层和隐藏 DOM。"""
        js = """
        const nodes = Array.from(document.querySelectorAll('button,a,span,div'));
        const target = nodes.find((el) => {
            const text = (el.innerText || el.textContent || '').trim();
            const rect = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            return text === '搜索'
                && rect.width > 0
                && rect.height > 0
                && style.visibility !== 'hidden'
                && style.display !== 'none';
        });
        if (target) {
            target.click();
            return true;
        }
        return false;
        """
        try:
            if page.run_js(js):
                self.log("已通过可见按钮触发搜索。")
                return True
        except Exception as exc:
            self.log(f"JS 搜索点击失败，尝试普通定位点击：{exc}")

        for selector in SEARCH_BUTTON_SELECTORS:
            try:
                for button in page.eles(selector):
                    if self.safe_click(button, "搜索按钮", raise_error=False):
                        self.log("已通过候选按钮触发搜索。")
                        return True
            except Exception:
                continue
        return False

    @staticmethod
    def safe_click(ele, desc: str = "元素", raise_error: bool = True) -> bool:
        """更稳的点击：普通点击失败时使用 JS 点击兜底。"""
        try:
            ele.click()
            return True
        except Exception as first_exc:
            try:
                ele.click(by_js=True)
                return True
            except Exception:
                try:
                    ele.run_js("this.click();")
                    return True
                except Exception as final_exc:
                    if raise_error:
                        raise RuntimeError(f"{desc}点击失败：{first_exc} / {final_exc}") from final_exc
                    return False

    def extract_text_from_child(self, card, selectors: Iterable[str]) -> str:
        """从卡片内部提取文本，失败时回退到卡片全文。"""
        child = self.find_first(card, selectors, timeout=1)
        if child:
            return (getattr(child, "text", "") or "").strip()
        return (getattr(card, "text", "") or "").strip()

    def extract_company_text(self, card) -> str:
        """提取公司名；选择器失败时从卡片底部文本粗略兜底。"""
        company = self.extract_text_from_child(card, COMPANY_SELECTORS)
        company = normalize_boss_obfuscated_digits(company).strip()
        if company:
            # 选择器过宽时可能拿到多行，优先取像公司名的最后几行。
            lines = [line.strip() for line in company.splitlines() if line.strip()]
            if lines:
                return lines[-1]

        text = normalize_boss_obfuscated_digits((getattr(card, "text", "") or "")).strip()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) >= 2:
            return lines[-2]
        return ""

    def card_matches_experience(self, card, experience_filter: str, page_filter_applied: bool = False) -> bool:
        """根据卡片文本二次校验经验限制，防止页面筛选失效。"""
        if not experience_filter or experience_filter == "不限":
            return True

        text = normalize_boss_obfuscated_digits((getattr(card, "text", "") or ""))
        aliases = EXPERIENCE_ALIASES.get(experience_filter, [experience_filter])
        if any(alias in text for alias in aliases):
            return True

        # Boss 顶部筛选已生效时，部分卡片会显示“在校/应届”等短标签，
        # 也有卡片文本提取不完整。此时不因卡片侧缺词误杀。
        if page_filter_applied:
            known_experience_words = set(EXPERIENCE_OPTIONS + ["在校", "应届", "在校/应届", "校招"])
            if not any(word in text for word in known_experience_words):
                return True

        return False

    @staticmethod
    def find_blocked_company_keyword(company_text: str, card_text: str, blocked_companies: list[str]) -> str:
        """公司黑名单模糊匹配，命中返回关键词。"""
        company_lower = normalize_boss_obfuscated_digits(company_text or "").lower()
        card_lower = normalize_boss_obfuscated_digits(card_text or "").lower()
        for keyword in blocked_companies:
            key = keyword.strip().lower()
            if key and (key in company_lower or key in card_lower):
                return keyword
        return ""

    @staticmethod
    def wait_page_loaded_soft(page: ChromiumPage) -> None:
        """兼容性等待：优先等待页面加载，失败则短暂 sleep。"""
        try:
            page.wait.load_start(timeout=3)
        except Exception:
            pass
        try:
            page.wait.doc_loaded(timeout=10)
        except Exception:
            time.sleep(2)

    @staticmethod
    def safe_get_url(page: ChromiumPage) -> str:
        try:
            return page.url or ""
        except Exception:
            return ""

    @staticmethod
    def safe_get_title(page: ChromiumPage) -> str:
        try:
            return page.title or ""
        except Exception:
            return ""


class BossAutoGreeterApp(ctk.CTk):
    """CustomTkinter 桌面 GUI。"""

    def __init__(self):
        super().__init__()
        self.title("Boss直聘自动打招呼助手")
        self.geometry("1080x680")
        self.minsize(980, 620)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.log_queue: Queue[str] = Queue()
        self.worker_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()

        self._build_ui()
        self.after(120, self._drain_log_queue)

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=0, minsize=310)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(self, corner_radius=8)
        left.grid(row=0, column=0, sticky="nsew", padx=(16, 10), pady=16)
        left.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(left, text="控制台", font=ctk.CTkFont(size=22, weight="bold"))
        title.grid(row=0, column=0, sticky="w", padx=18, pady=(18, 10))

        self.keyword_var = ctk.StringVar(value="后端开发")
        self.city_var = ctk.StringVar(value="杭州")
        self.min_salary_var = ctk.StringVar(value="18")
        self.max_count_var = ctk.StringVar(value="50")
        self.experience_var = ctk.StringVar(value="不限")
        self.blocked_companies_var = ctk.StringVar(value="")

        self._add_labeled_entry(left, "目标岗位关键词", self.keyword_var, 1)
        self._add_labeled_entry(left, "工作地点", self.city_var, 2)
        self._add_labeled_option(left, "工作经验限制", self.experience_var, EXPERIENCE_OPTIONS, 3)
        self._add_labeled_entry(left, "期望薪资下限（K）", self.min_salary_var, 4)
        self._add_labeled_entry(left, "最大沟通数量", self.max_count_var, 5)
        self._add_labeled_entry(left, "公司限制（用；分割）", self.blocked_companies_var, 6)

        self.test_button = ctk.CTkButton(left, text="测试浏览器连接", command=self.on_test_connection, height=40)
        self.test_button.grid(row=7, column=0, sticky="ew", padx=18, pady=(18, 8))

        self.start_button = ctk.CTkButton(left, text="开始运行应用", command=self.on_start, height=42)
        self.start_button.grid(row=8, column=0, sticky="ew", padx=18, pady=8)

        self.stop_button = ctk.CTkButton(
            left,
            text="强制停止",
            command=self.on_stop,
            height=42,
            fg_color="#8b1e2d",
            hover_color="#a32639",
        )
        self.stop_button.grid(row=9, column=0, sticky="ew", padx=18, pady=8)

        hint = (
            "运行前请先启动 Edge：\n"
            "\"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe\" "
            "--remote-debugging-port=9222 "
            "--user-data-dir=\"C:\\tmp\\BossAutoGreeterProfile\""
        )
        self.hint_label = ctk.CTkLabel(left, text=hint, justify="left", wraplength=260, text_color="#a9b4c2")
        self.hint_label.grid(row=10, column=0, sticky="ew", padx=18, pady=(18, 12))

        right = ctk.CTkFrame(self, corner_radius=8)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 16), pady=16)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        log_title = ctk.CTkLabel(right, text="运行日志", font=ctk.CTkFont(size=22, weight="bold"))
        log_title.grid(row=0, column=0, sticky="w", padx=18, pady=(18, 10))

        self.log_textbox = ctk.CTkTextbox(right, state="disabled", wrap="word", font=ctk.CTkFont(size=14))
        self.log_textbox.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))

        self.log_to_ui("应用已启动。请先登录接管的 Edge 浏览器，再点击测试或开始。")

    @staticmethod
    def _add_labeled_entry(parent, label_text: str, variable: ctk.StringVar, row: int) -> None:
        wrapper = ctk.CTkFrame(parent, fg_color="transparent")
        wrapper.grid(row=row, column=0, sticky="ew", padx=18, pady=8)
        wrapper.grid_columnconfigure(0, weight=1)

        label = ctk.CTkLabel(wrapper, text=label_text, anchor="w")
        label.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        entry = ctk.CTkEntry(wrapper, textvariable=variable, height=38)
        entry.grid(row=1, column=0, sticky="ew")

    @staticmethod
    def _add_labeled_option(parent, label_text: str, variable: ctk.StringVar, values: list[str], row: int) -> None:
        wrapper = ctk.CTkFrame(parent, fg_color="transparent")
        wrapper.grid(row=row, column=0, sticky="ew", padx=18, pady=8)
        wrapper.grid_columnconfigure(0, weight=1)

        label = ctk.CTkLabel(wrapper, text=label_text, anchor="w")
        label.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        option = ctk.CTkOptionMenu(wrapper, variable=variable, values=values, height=38)
        option.grid(row=1, column=0, sticky="ew")

    def log_to_ui(self, message: str) -> None:
        """线程安全日志入口：后台线程只入队，真正写 UI 由主线程完成。"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_queue.put(f"[{timestamp}] {message}")

    def _drain_log_queue(self) -> None:
        try:
            while True:
                line = self.log_queue.get_nowait()
                self.log_textbox.configure(state="normal")
                self.log_textbox.insert("end", line + "\n")
                self.log_textbox.configure(state="disabled")
                self.log_textbox.see("end")
        except Empty:
            pass
        self.after(120, self._drain_log_queue)

    def on_test_connection(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            self.log_to_ui("当前已有任务正在运行，请先停止或等待结束。")
            return

        self.stop_event.clear()
        self.worker_thread = threading.Thread(target=self._test_connection_worker, daemon=True)
        self.worker_thread.start()

    def on_start(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            self.log_to_ui("当前已有任务正在运行。")
            return

        try:
            keyword = self.keyword_var.get().strip() or "后端开发"
            city = self.city_var.get().strip() or "杭州"
            experience_filter = self.experience_var.get().strip() or "不限"
            blocked_companies = split_blocked_companies(self.blocked_companies_var.get().strip())
            min_salary_k = int(self.min_salary_var.get().strip())
            max_count = int(self.max_count_var.get().strip())
            if min_salary_k <= 0 or max_count <= 0:
                raise ValueError
        except ValueError:
            self.log_to_ui("参数错误：薪资下限和最大沟通数量必须为正整数。")
            return

        self.stop_event.clear()
        self.worker_thread = threading.Thread(
            target=self._run_worker,
            args=(keyword, city, min_salary_k, max_count, experience_filter, blocked_companies),
            daemon=True,
        )
        self.worker_thread.start()

    def on_stop(self) -> None:
        self.stop_event.set()
        self.log_to_ui("已发送强制停止信号，后台线程会在当前等待或点击动作结束后停止。")

    def _test_connection_worker(self) -> None:
        try:
            BossAutoGreeter(self.log_to_ui, self.stop_event).test_connection()
        except Exception as exc:
            self.log_to_ui(f"浏览器连接测试失败：{exc}")
            self.log_to_ui("请确认 Edge 已按 9222 端口命令启动，并且没有被其他程序独占。")

    def _run_worker(
        self,
        keyword: str,
        city: str,
        min_salary_k: int,
        max_count: int,
        experience_filter: str,
        blocked_companies: list[str],
    ) -> None:
        try:
            BossAutoGreeter(self.log_to_ui, self.stop_event).run(
                keyword,
                city,
                min_salary_k,
                max_count,
                experience_filter,
                blocked_companies,
            )
        except Exception as exc:
            self.log_to_ui(f"任务异常终止：{exc}")
            self.log_to_ui(traceback.format_exc())


if __name__ == "__main__":
    app = BossAutoGreeterApp()
    app.mainloop()
