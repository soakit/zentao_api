#-*- coding: UTF-8 -*- 
import argparse
import csv
import requests
import json
from datetime import datetime

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

    # 用户列表
    def get_user_list(self):
        if ZentaoCli.userList is None or self.override:
            req_url = self.get_api("user_list")
            query_data = self.s.get(req_url).json()
            json_query_data = json.loads(query_data['data'])
            json_query_data['users']
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
            return ZentaoCli.userList, user_map

    def clean_title(self, title):
        # title = title.replace('【生产环境】', '').replace('【生产环境-1.0】', '').replace('【生产环境-易销存】', '').replace('【生产环境-2.0】', '').replace('【生产环境-供应链】', '')
        
        title = title.strip()
        return title

    def get_days_between_dates(self, start_date, end_date):
        # Calculate the difference as a timedelta object
        time_difference = end_date - start_date
        # Get the total difference in seconds
        total_seconds = time_difference.total_seconds()
        # Calculate the difference in days as a float
        # There are 60 * 60 * 24 = 86400 seconds in a day
        diffDays_float = total_seconds / 86400
        # Round the float result to 2 decimal places
        diffDays = round(diffDays_float, 2)
        return diffDays
    

    # 获取团队成员生产bug
    def get_myteam_bug(self, project_id, query_id):
        user_list, user_map = self.get_user_list()
        bug_list = []
        
        # print(user_map)

        # 1     易订货1.0
        # 18    供应链
        # 27    易订货2.0

        ranges = [query_id]
        
        # print(ranges)

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
                    assignedDateTime = datetime.strptime(item['assignedDate'], '%Y-%m-%d %H:%M:%S')
                    diffAssignedDays = self.get_days_between_dates(openDateTime, assignedDateTime)                    
                    item['assignedDays'] = diffAssignedDays
                    item['solvedDays'] = None
                    
                    if item['status'] in ['resolved', 'closed']:      
                        resolvedDateTime = datetime.strptime(item['resolvedDate'], '%Y-%m-%d %H:%M:%S')
                        diffResolvedDays = self.get_days_between_dates(openDateTime, resolvedDateTime)
                        item['assignedDays'] = None
                        item['solvedDays'] = diffResolvedDays
                    else:
                        item['solvedDays'] = None
                    
                    frontEnds = ['wangjie', 'jianxf', 'yuanyang', 'liuchang', 'tangwf', 'likg', 'qiuyq', 'liujc', 'mayy']
                    # 无效的BUG包括： 设计如此（bydesign）、 重复BUG（duplicate）、 转为需求（tostory）、 不是BUG（notbug）， 外部原因（external）
                    invalidBug = ['duplicate', 'notbug', 'external', 'bydesign', 'tostory']
                    
                    # 标题不包含"疑难"
                    # "疑难" not in item['title'] and 
                    if item['assignedTo'] in frontEnds or item['resolvedBy'] in frontEnds and item['resolution'] not in invalidBug:  
                        bug_list.append({
                            # '编号': '{}（by {}）'.format(item['id'], user_map.get(item['openedBy'].lower(), '未知用户')),
                            '编号': item['id'],
                            '标题': self.clean_title(item['title']),
                            '链接': self.get_api("bug_detail_html").format(item['id']),
                            '状态': item['status'],
                            '创建日期': item['openedDate'],
                            '指派日期': item['assignedDate'],
                            '指派天数': item['assignedDays'],
                            '指派者': user_map.get(item['assignedTo'].lower(), '未知用户'),
                            '创建者': user_map.get(item['openedBy'].lower(), '未知用户'),
                            '解决者': item['resolvedBy'] and user_map.get(item['resolvedBy'].lower(), '未知用户'),
                            '解决方案': item['resolution'],
                            '解决日期': item['resolvedDate'],
                            '解决天数': item['solvedDays'],
                    })

        return bug_list

if __name__ == "__main__":
    # 创建参数解析器
    parser = argparse.ArgumentParser(description='前端团队生产bug处理提醒')
    parser.add_argument('--username', required=True, help='禅道用户名')
    parser.add_argument('--password', required=True, help='禅道密码')

    # 解析命令行参数
    args = parser.parse_args()

    cli = ZentaoCli("https://pms.dinghuo123.com", args.username, args.password, override=False)
    cli.login()
    
    query_id = 'myQueryID--1000-1000-1'
    
    startDate = '2025-04-01'
    endDate = '2025-06-30'
    
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
            # 'andOr3': 'and',
            # 'field3': 'status',
            # 'operator3': '=',
            # 'value3': 'active',
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
        print('查询{}项目bug中...'.format(project_id))
        bug = cli.get_myteam_bug(project_id, query_id)
        print('{}项目bug查询完成'.format(project_id))
        allBug.extend(bug)
    
    # 将allBug写入allBugs.json文件
    with open('2025二季度前端bug.json', 'w', encoding='utf-8') as f:
        json.dump(allBug, f, ensure_ascii=False, indent=4)
    
    # 将allBug写入到csv文件
    with open('2025二季度前端bug.csv', 'w', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['编号', '标题', '链接', '状态', '创建日期', '指派日期', '指派天数',  '指派者', '创建者', '解决者','解决方案', '解决日期', '解决天数'])
        for item in allBug:
            writer.writerow([item['编号'], item['标题'], item['链接'], item['状态'], item['创建日期'], item['指派日期'], item['指派天数'], item['指派者'], item['创建者'], item['解决者'], item['解决方案'], item['解决日期'], item['解决天数']])


