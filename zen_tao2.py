#-*- coding: UTF-8 -*- 
import argparse
import csv
import requests
import json
import re
import time
from datetime import datetime, timedelta

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
            "search_buildQuery": '/search-buildQuery',
            # bug-browse-27-0-bySearch-myQueryID.html
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
        # title = title.replace('【生产环境】', '').replace('【生产环境-1.0】', '').replace('【生产环境-易销存】', '').replace('【生产环境-2.0】', '').replace('【生产环境-供应链】', '')
        
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
    def get_myteam_bug(self, project_id, query_id):
        user_list, user_map = self.get_user_list()
        bug_list = []
        
        # print(user_map)

        print('查询{}项目bug中...'.format(project_id))

        # 1     易订货1.0
        # 18    供应链
        # 27    易订货2.0

        ranges = [query_id]
        
        print(ranges)

        for project_id in [project_id]:  # 遍历1, 18, 27
            for condition in ranges:  # 循环区间
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
                    
                    # 解决天数：
                    # 1. 先将创建时间和解决时间转换为毫秒数
                    # 2. 然后解决时间-创建时间的毫秒数差值计算天数。
                    # 3. 计算的天数要减掉解决时间和创建时间中间的节假日天数
                    # 4. 天数保留2位小数
                    # eg:
                    # 创建时间："openedDate": "2023-09-08 10:36:33",
                    # 解决时间："resolvedDate": "2023-09-08 18:36:33",
                    # 解决天数：1.5天
                    
                    openDateTime = datetime.strptime(item['openedDate'], '%Y-%m-%d %H:%M:%S')
                    resolveDateTime = datetime.strptime(item['resolvedDate'], '%Y-%m-%d %H:%M:%S')
                    
                    # Calculate the difference as a timedelta object
                    time_difference = resolveDateTime - openDateTime
                    # Get the total difference in seconds
                    total_seconds = time_difference.total_seconds()
                    # Calculate the difference in days as a float
                    # There are 60 * 60 * 24 = 86400 seconds in a day
                    diffDays_float = total_seconds / 86400
                    # Round the float result to 2 decimal places
                    diffDays = round(diffDays_float, 2)

                    item['solve_days'] = diffDays
                    
                    frontEnds = ['wangjie', 'jianxf', 'yuanyang', 'liuchang', 'tangwf', 'likg', 'qiuyq', 'liujc', 'mayy']
                    # 无效的BUG包括： 设计如此（bydesign）、 重复BUG（duplicate）、 转为需求（tostory）、 不是BUG（notbug）， 外部原因（external）
                    invalidBug = ['duplicate', 'notbug', 'external', 'bydesign', 'tostory']
                    
                    # item['solve_days'] > 1 and
                    # 标题不包含"疑难"
                    if "疑难" not in item['title'] and item['resolvedBy'] in frontEnds and item['resolution'] not in invalidBug:  
                        bug_list.append({
                            # '编号': '{}（by {}）'.format(item['id'], user_map.get(item['openedBy'].lower(), '未知用户')),
                            '编号': item['id'],
                            '标题': self.clean_title(item['title']),
                            '解决者': user_map.get(item['resolvedBy'].lower(), '未知用户'),
                            '链接': self.get_api("bug_detail_html").format(item['id']),
                            '创建日期': item['openedDate'],
                            '指派日期': item['assignedDate'],
                            '解决日期': item['resolvedDate'],
                            '解决天数': item['solve_days'],
                            '解决方案': item['resolution'],
                    })

        return bug_list

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
    
    query_id = 'myQueryID--1000-1000-1'
    
    startDate = '2025-01-01'
    endDate = '2025-03-31'
    
    project_ids = [27, 18, 1]
    
    allBug = []
    
    for project_id in project_ids:
        # 构造禅道查询条件
        params = {
            'fieldconfirmed': 'ZERO',
            'fieldproduct': project_id,
            'fieldmodule': 'ZERO',
            'fieldseverity': '0',
            'fieldpri': '0',
            'andOr1': 'AND',
            'field1': 'title',
            'operator1': 'notinclude',
            'value1': '疑难',
            'andOr2': 'and',
            'field2': 'title',
            'operator2': 'include',
            'value2': '生产环境',
            'andOr3': 'and',
            'field3': 'status',
            'operator3': '!=',
            'value3': 'active',
            'groupAndOr': 'and',
            'andOr4': 'AND',
            'field4': 'openedDate',
            'operator4': '>=',
            'value4': startDate,
            'andOr5': 'and',
            'field5': 'openedDate',
            'operator5': '<=',
            'value5': endDate,
            'andOr6': 'and',
            'field6': 'resolution',
            'operator6': 'notinclude',
            'value6': 'notbug',
            'module': 'bug',
            'actionURL': '/bug-browse-{}-0-bySearch-{}.html'.format(project_id, query_id),
            'groupItems': '3',
            'formType': 'more',
        }
        search_buildQuery = cli.s.post(cli.get_api('search_buildQuery'), params)
        bug = cli.get_myteam_bug(project_id, query_id)
        allBug.extend(bug)
    
    # print(search_buildQuery.text)
    # print(allBug)

    # 我的团队bug
    # bug_list, reminder_list = cli.get_myteam_bug()
    # reminder_list = sorted(reminder_list, key=lambda x: x['剩余天数'])

    # 缩减title的宽度，超出使用省略号
    # for item in reminder_list:
    #     item['标题'] = item['标题'][:20] + '...' if len(item['标题']) > 20 else item['标题']

    # 以表格形式输出到控制台
    # headers = {
    #     '编号': '编号',
    #     '操作人': '操作人',
    #     '指派人': '指派人',
    #     '指派日期': '指派日期',
    #     '截止日期': '截止日期',
    #     '剩余天数': '剩余天数',
    #     '标题': '标题'
    # }
    
    # print(tabulate(allBug, headers=headers, tablefmt='grid'))
    
    # 将allBug写入allBugs.json文件
    with open('allBugs.json', 'w', encoding='utf-8') as f:
        json.dump(allBug, f, ensure_ascii=False, indent=4)
    
    # 将allBug写入到csv文件
    with open('allBugs.csv', 'w', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['编号', '标题', '解决者', '链接', '创建日期', '指派日期', '解决日期', '解决天数', '解决方案'])
        for item in allBug:
            writer.writerow([item['编号'], item['标题'], item['解决者'], item['链接'], item['创建日期'], item['指派日期'], item['解决日期'], item['解决天数'], item['解决方案']])


