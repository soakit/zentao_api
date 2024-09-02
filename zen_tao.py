#-*- coding: UTF-8 -*- 
import argparse
import requests
import json
import re
import time
from datetime import datetime, timedelta
from tabulate import tabulate


class ZentaoCli(object):
    session = None   # 用于实现单例类，避免多次申请sessionID
    sid = None
    userList = None
    buildBranchList = None

    def __init__(self, url, account, password, override=False):
        self.url = url
        self.account = account   # 账号
        self.password = password   # 密码
        self.override = override    # 是否覆盖原会话
        self.pages = {
            "login": "/user-login.html",  # 登录的接口
            "get_session_id": "/api-getsessionid.json",  # 获取sessionId sessionName
            "my_bug": "/my-bug.json",  # 获取bug列表 json
            "my_bug_html": "/my-bug.html",  # 获取bug列表 html
            "user_list": "/company-browse-0-bydept-id-69-100-1.json",  # 获取研发部成员列表
            "bug_detail": "/bug-view-{}.json",  # bug 详情
            "bug_detail_html": "/bug-view-{}.html",  # bug 详情的 uid  服了， 这Tmd设计的什么鬼神api
            "project_bug_list_with_search": '/bug-browse-{}-0-bySearch-{}.json',
            "resolve_bug": "/bug-resolve-{}.html?onlybody=yes",  # 解决bug
            "build_branch": '/project-build-220-42.json',  # 跨运管家版本分支
            'file_read': '/file-read-{}',  # 文件读取
        }
        self.s = None
        self.sid = None

    # 获取api地址
    def get_api(self, api_name, **args):
        return self.url.rstrip("/") + self.pages[api_name]

    @staticmethod
    def req(self, url):
        web = self.s.get(url)
        if web.status_code == 200:
            resp = json.loads(web.content)
            if resp.get("status") == "success":
                return True, resp
            else:
                return False, resp

    # 登录
    def login(self):
        if self.s is None:
            if not self.override and ZentaoCli.session is not None:
                self.s = ZentaoCli.session
            else:
                # 新建会话
                self.s = requests.session()
                # print(self.url)
                res, resp = self.req(self, self.url.rstrip("/") + self.pages['get_session_id'])
                # print(res, resp)
                if res:
                    print("获取sessionID成功")
                    self.sid = json.loads(resp["data"])["sessionID"]
                    ZentaoCli.sid = self.sid
                    login_res = self.s.post(
                        url=self.url.rstrip("/") + self.pages["login"],
                        params={'account': self.account, 'password': self.password, 'sid': self.sid}
                    )
                    if login_res.status_code == 200:
                        print("登录成功")
                        ZentaoCli.session = self.s

    # bug分支版本列表
    def get_build_branch(self):
        if ZentaoCli.buildBranchList is None or self.override:
            req_url = self.get_api("build_branch")
            query_data = self.s.get(req_url).json()
            json_query_data = json.loads(query_data['data'])
            # print(json_query_data)
            build_branch_list = []
            build_branch_map = {}
            for item in json_query_data['projectBuilds']['42']:
                build_branch_list.append({
                    'name': item['name'],
                    'id': item['id'],
                    'builder': item['builder'],
                })
                build_branch_map[item['name']] = item['id']
            if build_branch_map is not None:
                ZentaoCli.buildBranchList = build_branch_list
            print('fetch branch list')
            return build_branch_list, build_branch_map
        else:
            build_branch_map = {}
            for item in ZentaoCli.buildBranchList:
                build_branch_map[item['name']] = item['id']
            print('local branch list')
            return ZentaoCli.buildBranchList, build_branch_map

    # 用户列表
    def get_user_list(self):
        if ZentaoCli.userList is None or self.override:
            req_url = self.get_api("user_list")
            query_data = self.s.get(req_url).json()
            json_query_data = json.loads(query_data['data'])
            json_query_data['users'].extend([
                {
                    'id': '0',
                    'account': 'liya.lei',
                    'realname': '雷雅丽',
                },
                {
                    'id': '1',
                    'account': 'joyce.zhang',
                    'realname': '张晶',
                },
                {
                    'id': '2',
                    'account': 'skinny.li',
                    'realname': '李清娴',
                },
                {
                    'id': '2',
                    'account': 'june.chu',
                    'realname': '储君',
                },
            ])
            user_list = []
            user_map = {}
            for item in json_query_data['users']:
                user_list.append({
                    'id': item['id'],
                    'account': item['account'].lower(),
                    'realname': item['realname'],
                })
                user_map[item['account']] = item['realname']
            if user_map is not None:
                ZentaoCli.userList = user_list
            return user_list, user_map
        else:
            user_map = {}
            for item in ZentaoCli.userList:
                user_map[item['account']] = item['realname']
            print('local user list')
            return ZentaoCli.userList, user_map

    def clean_title(self, title):
        title = title.replace('【生产环境】', '').replace('【生产环境-1.0】', '').replace('【生产环境-易销存】', '').replace('【生产环境-2.0】', '')
        title = title.strip()
        return title

    # 获取bug列表
    def get_my_bug(self):
        req_url = self.get_api('my_bug')
        query_data = self.s.get(req_url).json()
        json_query_data = json.loads(query_data['data'])
        bug_list = []
        user_list, user_map = self.get_user_list()

        for item in json_query_data['bugs']:
            bug_list.append({
                'uid': item['id'],
                'title': '{}（by {}）'.format(item['id'], user_map[item['openedBy'].lower()]),
                'subtitle': self.clean_title(item['title']),
                'arg': self.get_api("bug_detail_html").format(item['id']),
            })

        return bug_list

    # 获取团队成员生产bug
    def get_myteam_bug(self):
        user_list, user_map = self.get_user_list()
        bug_list = []
        reminder_list = []  # 提醒列表

        print('查询团队bug中...')

        # 1     易订货1.0
        # 18    供应链
        # 27    易订货2.0

        # condition
        # 丽姿生产bug -> 541
        # 妙凤生产bug -> 540
        # 炜峰生产bug -> 539
        # 慧琳生产bug -> 538
        # 雨晴生产bug -> 537
        # 于辉生产bug -> 536
        # 刘畅生产bug -> 535
        # 锦坤生产bug -> 534
        # 成双生产bug -> 533
        # 533 ~ 541
        for project_id in [18, 27, 1]:  # 遍历1, 18, 27
            for condition in range(533, 542):  # 循环533~541
                req_url = self.get_api('project_bug_list_with_search').format(project_id, condition)
                response = self.s.get(req_url)
                try:
                    query_data = response.json()
                except requests.exceptions.JSONDecodeError:
                    # 打印原始响应内容以便调试
                    print("JSON解析错误，原始响应内容：", response.text)
                    continue

                json_query_data = json.loads(query_data['data'])
                
                for item in json_query_data['bugs']:
                    # severity bug等级
                    # title 标题
                    # assignedDate 指派日期

                    # 处理规则
                    # ● 一级BUG 当天处理；
                    # ● 二级BUG 3个工作日内处理，疑难问题10个工作日内处理；
                    # ● 三级BUG 3个工作日内处理，疑难问题20个工作日内处理；
                    # ● 四级BUG 30个工作日内处理。

                    bug_list.append({
                        '编号': '{}（by {}）'.format(item['id'], user_map.get(item['openedBy'].lower(), '未知用户')),
                        '标题': self.clean_title(item['title']),
                        # '链接': self.get_api("bug_detail_html").format(item['id']),
                        '操作人': user_map.get(item['openedBy'].lower(), '未知用户'),
                        '指派人': user_map.get(item['assignedTo'].lower(), '未知用户'),
                        '指派日期': item['assignedDate']
                    })

                    # 计算截止日期
                    severity = item['severity']
                    is_difficult = '疑难问题' in item['title']
                    # eg: "assignedDate": "2023-09-08 10:36:33",
                    assigned_date_str = item['assignedDate'].split(' ')[0]  # 提取日期部分
                    assigned_date = datetime.strptime(assigned_date_str, '%Y-%m-%d')
                    final_date = assigned_date
                    if severity == '2':
                        final_date = self.add_business_days(assigned_date, 10 if is_difficult else 3)
                    elif severity == '3':
                        final_date = self.add_business_days(assigned_date, 20 if is_difficult else 3)
                    elif severity == '4':
                        final_date = self.add_business_days(assigned_date, 30)

                    current_date = datetime.now()
                    last_month = current_date - timedelta(days=current_date.day)
                    last_month_format = last_month.strftime("%Y-%m")
                    remaining_days = self.calculate_remaining_business_days(final_date)

                    if assigned_date.strftime('%Y-%m') >= last_month_format:
                        reminder_list.append({
                            '编号': item['id'],
                            '标题': self.clean_title(item['title']),
                            '操作人': user_map.get(item['openedBy'].lower(), '未知用户'),
                            '指派人': user_map.get(item['assignedTo'].lower(), '未知用户'),
                            '指派日期': item['assignedDate'],
                            '截止日期': final_date.strftime('%Y-%m-%d'),
                            '剩余天数': remaining_days
                        })

        print('查询团队bug成功')
        return bug_list, reminder_list

    def add_business_days(self, start_date, days):
        """
        添加工作日，跳过中国的法定节假日
        """
        holidays = self.get_holidays()  # 获取中国的法定节假日列表
        current_date = start_date
        added_days = 0
        while added_days < (days - 1):
            current_date += timedelta(days=1)
            if current_date.weekday() < 5 and current_date not in holidays:  # 周一到周五且不是节假日
                added_days += 1
        return current_date

    def calculate_remaining_business_days(self, final_date):
        current_date = datetime.now()
        remaining_days = 0
        holidays = self.get_holidays()  # 获取中国的法定节假日列表
        while current_date < final_date:
            current_date += timedelta(days=1)
            if current_date.weekday() < 5 and current_date not in holidays:  # 周一到周五且不是节假日
                remaining_days += 1
        return remaining_days

    def get_holidays(self):
        """
        获取中国的法定节假日列表
        """
        current_date = datetime.now()
        response = requests.get('http://api.haoshenqi.top/holiday?date=' + str(current_date.year))
        """
        # eg:
        {
            "date": "2019-05-01",
            "year": 2019,
            "month": 5,
            "day": 1,
            "status": 3
        }
        status说明: 
            0 普通工作日
            1 周末双休日
            2 需要补班的工作日
            3 法定节假日
        """
        holidays_data = response.json()

        # 过滤出节假日和周末
        holidays = [datetime.strptime(holiday['date'], '%Y-%m-%d') for holiday in holidays_data if holiday['status'] in [1, 3]]
        return holidays

    # 获取bug 详情
    def get_bug_detail(self, bug_id):
        req_url = self.get_api("bug_detail").format(bug_id)
        query_data = self.s.get(req_url).json()
        json_query_data = json.loads(query_data['data'])
        return json_query_data

    # 解析html获取bug详情的 uid
    def get_bug_uid(self, bug_id):
        req_url = self.get_api("bug_detail_html").format(bug_id)
        res = self.s.get(req_url)
        res.encoding = 'utf-8'    # 使用utf-8对内容编码
        if res.status_code == 200:
            html = res.content.decode()
            uid = re.findall('var kuid = \'(.*?)\'', html)
            return uid[0]
        else:
            return None

    # 解决bug
    def resolve_bug(self, bug_id, *arg):
        uid = self.get_bug_uid(bug_id)
        req_url = self.get_api("resolve_bug").format(bug_id)
        print(req_url)
        now_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        # build_branch_list, build_branch_map = self.get_build_branch()
        json_query_data = self.get_bug_detail(bug_id)
        print(json_query_data)
        bug_detail = json_query_data['bug']
        builds_detail = json_query_data['builds']
        users_detail = json_query_data['users']
        print(users_detail)
        print(bug_detail)
        params = {
            'resolution': 'fixed',
            'uid': uid,
            'resolvedDate': now_time,
            'assignedTo': bug_detail['openedBy'],  # 默认指给提出bug的测试人员
            'resolvedBuild': bug_detail['openedBuild'],  # 解决版本的分支id
            'comment': '--- commit comment by Alfred4 Workflow ---',
        }
        print(params)
        res = self.s.post(req_url, params)
        if res.status_code == 200:
            print('✅ bug #{} 已点解决 by {}'.format(bug_id, now_time))
        else:
            print('淦，bug #{} 没点掉 by {}'.format(bug_id, now_time))


if __name__ == "__main__":
    # 创建参数解析器
    parser = argparse.ArgumentParser(description='牛13团队生产bug处理提醒')
    parser.add_argument('--username', required=True, help='禅道用户名')
    parser.add_argument('--password', required=True, help='禅道密码')

    # 解析命令行参数
    args = parser.parse_args()

    cli = ZentaoCli("https://pms.dinghuo123.com", args.username, args.password, override=False)
    cli.login()
    # cli.get_user_list()
    # cli.get_build_branch()
    # cli.resolve_bug(10681)
    
    # 我的bug
    # my_bugs = cli.get_my_bug()
    # print(my_bugs)

    # 我的团队bug
    bug_list, reminder_list = cli.get_myteam_bug()
    reminder_list = sorted(reminder_list, key=lambda x: x['剩余天数'])

    # 缩减title的宽度，超出使用省略号
    for item in reminder_list:
        item['标题'] = item['标题'][:20] + '...' if len(item['标题']) > 20 else item['标题']

    # 以表格形式输出到控制台
    headers = {
        '编号': '编号',
        '操作人': '操作人',
        '指派人': '指派人',
        '指派日期': '指派日期',
        '截止日期': '截止日期',
        '剩余天数': '剩余天数',
        '标题': '标题'
    }
    
    print(tabulate(reminder_list, headers=headers, tablefmt='grid'))
    # 将reminder_list写入reminder.json文件
    with open('reminder.json', 'w', encoding='utf-8') as f:
        json.dump(reminder_list, f, ensure_ascii=False, indent=4)
    

