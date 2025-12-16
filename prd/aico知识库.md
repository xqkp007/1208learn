一、背景说明
该文档为知识库接口解析流程的说明文档，通过下述接口调用，可以实现知识库文件的上传、解析、切片、上线的过程。以下用测试的账号和知识库做示例，aico服务ip:20.17.39.132，用户名：mashuang，知识库名称：kb_mashuang,请修改自己的aico服务ip和知识库，重要字段将用红色标记
二、前置条件
1.在aico系统中创建用户，且角色权限为User/Admin
2.确认用户存在知识库，例如：
[图片]
三、接口说明
1.通过用户名和用户id获取token（用户名和用户id自己查询数据库获取）
a.接口调用URL:http://20.17.39.132:11105/aicoapi/user/generate_user_token
b.请求方式：POST
c.请求参数：
字段
类型
长度
是否必填
描述
username
string
50
是
用户名
user_id
int
50
是
用户id
d.请求示例：
curl --location 'http://20.17.39.132:11105/aicoapi/user/generate_user_token' \
--header 'Content-Type: application/json' \
--data '{
    "username": "mashuang",
    "user_id": 1034
}'
e.响应示例：
{
    "code": 200,
    "msg": "success",
    "data": {
        "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOnsidXNlcm5hbWUiOiJtYXNodWFuZyIsInVzZXJfaWQiOiIxMDM0In0sImV4cCI6MTc2MzYwNzQ2MX0.ORHDS3_FW6amrD6_wr1WUGTDRvxYCb8eAGQk-1UEMm0"
    }
}

2.根据用户名查询项目id,也就是pid
a.接口调用URL:http://20.17.39.132:39810/api/project_manage/projects/search_project
b.请求方式：GET
c.请求参数：
字段
类型
长度
是否必填
描述
project_name
string
50
是
项目名称，也就是用户名
d.请求示例：
curl --location 'http://20.17.39.132:39810/api/project_manage/projects/search_project?project_name=mashuang' \
--header 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOnsidXNlcm5hbWUiOiJtYXNodWFuZyIsInVzZXJfaWQiOiIxMDM0In0sImV4cCI6MTc2MzYwNzQ2MX0.ORHDS3_FW6amrD6_wr1WUGTDRvxYCb8eAGQk-1UEMm0'
e.响应参数：
字段
类型
长度
是否必传
描述
id
string
50
是
项目id
project_name
string
50
是
项目名称
status
string
50
是
项目状态
f.响应示例：
{
    "total": 1,
    "type": "info",
    "error": null,
    "message": "完成",
    "data": [
        {
            "id": 1783,
            "project_name": "mashuang",
            "project_function": [],
            "status": "下线完成"
        }
    ],
    "start_time": 1761016561369,
    "end_time": 1761016561369,
    "err_code": 0,
    "page_index": 0,
    "page_size": 0
}

3.创建知识库
a.接口调用URL:http://20.17.39.132:39810/api/project_manage/projects/search_project
b.请求方式：POST
c.请求参数：
字段
类型
长度
是否必填
描述
user_id
string
50
是
用户名称
kb_display_name
string
50
是
知识库显示名称
kb_name
string
50
是
知识库名称
kb_desc
string
50
是
知识库描述
pid
int
5
是
项目id
d.请求示例：
curl --location 'http://20.17.39.132:11105/aicoapi/kb_manage/kbm/create_kb' \
--header 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOnsidXNlcm5hbWUiOiJhZG1pbiIsInVzZXJfaWQiOiI5OTkifSwiZXhwIjoxNzYzNjIxNTczfQ.fqQHS0HnXGScjMgPqTHNi5auXWyKqhE-ZRTwNLF3hz4' \
--header 'Content-Type: application/json' \
--data '{
    "user_id": 999,
    "kb_display_name": "test1",
    "kb_name": "test2",
    "kb_desc": "test2",
    "pid": 1777
}'
e.响应示例：
{
    "total": null,
    "type": "info",
    "error": null,
    "message": "完成",
    "data": "",
    "start_time": 1761033515223,
    "end_time": 1761033515223,
    "err_code": 0,
    "page_index": null,
    "page_size": null
}

4.根据知识库名称和pid查询指定知识库的kb_id
a.接口调用URL:http://20.17.39.132:11105/aicoapi/kb_manage/kbm/search_kb
b.请求方式：GET
c.请求参数：
字段
类型
长度
是否必填
描述
pid
int
10
是
项目id
view_type
string
50
是

查询类型--
personal/个人知识库
official/部门知识库
all/所有知识库
kb_name
string
50
是
知识库名称
d.请求示例：
curl --location 'http://20.17.39.132:11105/aicoapi/kb_manage/kbm/search_kb?pid=1783&view_type=personal&kb_name=kb_mashuang' \
--header 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOnsidXNlcm5hbWUiOiJtYXNodWFuZyIsInVzZXJfaWQiOiIxMDM0In0sImV4cCI6MTc2MzYwNjg5MX0.TMh344cwSmwOMyHD6VVggkqxyHOfWyH-5TGuMzRF7ZU'
e.响应参数：
字段
类型
长度
是否必传
描述
id
string
50
是
知识库id
project_id
string
50
是
项目id
kb_name
string
50
是
知识库名称
kb_display_name
string
100
是
知识库显示名称
kb_desc
string
200
是
知识库描述
file_num
int
5
是
文件数量
k_num
int
5
是
切片数量
operator
string
50
是
操作人
f.响应示例：
{
    "status": 200,
    "msg": "查询成功",
    "data": [
        {
            "id": 1675,
            "project_id": 1783,
            "kb_name": "kb_mashuang",
            "kb_display_name": "kb_mashuang",
            "kb_desc": "kb_mashuang是该项目的默认数据库",
            "file_num": 2,
            "k_num": 10,
            "operator": "system",
            "create_time": "2025-07-31T14:48:29",
            "update_time": "2025-09-09T13:59:58"
        }
    ],
    "total": 1
}

5.上传知识库文件
a.接口调用URL:http://20.17.39.132:11105/aicoapi/knowledge_manage/file/upload
b.请求方式：POST
c.请求参数：
字段
类型
长度
是否必填
描述
pid
int
5
是
项目id
kb_id
int
5
是
知识库
source

int
5
是
素材来源--
1/手动
2/接口
oper
int
5
是
是否覆盖--
1/覆盖
2/不覆盖
files
file

是
文件实体
d.请求示例：
curl --location 'http://20.17.39.132:11105/aicoapi/knowledge_manage/file/upload' \
--header 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOnsidXNlcm5hbWUiOiJtYXNodWFuZyIsInVzZXJfaWQiOiIxMDM0In0sImV4cCI6MTc2MzYwNjg5MX0.TMh344cwSmwOMyHD6VVggkqxyHOfWyH-5TGuMzRF7ZU' \
--form 'pid="1783"' \
--form 'kb_id="1675"' \
--form 'source="1"' \
--form 'oper="1"' \
--form 'files=@"/path/to/file"'
e.响应示例：
{
    "message": "文件接收成功，正在后台上传",
    "err_code": 0
}
备注：上传文件为异步上传
6.获取文件列表信息
a.接口调用URL:http://20.17.39.132:11105/aicoapi/knowledge_manage/file/show
b.请求方式：POST
c.请求参数：
字段
类型
长度
是否必填
描述
title
string
50
是
文件名称
pid
int
5
是
项目id
kb_id
int
5
是
知识库id
view_type

string
25

是
查询类型--
personal/个人知识库
official/部门知识库
all/所有知识库
type
int

1

是
切分类型--
1/长度切分  
2/目录切分
3/按照行 
4/按照列 
5/自动切分 
6/自定义切分（按照正则）
7/按照页切分
d.请求示例：
curl --location 'http://20.17.39.132:11105/aicoapi/knowledge_manage/file/show' \
--header 'Login-Type: NORMAL' \
--header 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOnsidXNlcm5hbWUiOiJtYXNodWFuZyIsInVzZXJfaWQiOiIxMDM0In0sImV4cCI6MTc2MzYwNjg5MX0.TMh344cwSmwOMyHD6VVggkqxyHOfWyH-5TGuMzRF7ZU' \
--header 'Referer: http://20.17.39.132:11105/ai_worker/knowledgeBase?tab=1&kId=1675' \
--header 'X-Trace-ID: 680aaeb21490338320b92339205513c2' \
--header 'Traceparent: 00-680aaeb21490338320b92339205513c2-96fca4eac8692f79-01' \
--header 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36' \
--header 'Accept: application/json, text/plain, */*' \
--header 'Content-Type: application/json' \
--data '{
    "title": "公告第37号.pdf",
    "pid": 1783,
    "kb_id": "1675",
    "view_type": "personal",
    "type": "1"
}'
e.响应参数：
字段
类型
长度
是否必传
描述
id
int
50
是
文件id
project_id
int
50
是
项目id
kb_id
int
50
是
知识库id
file_name
string
100
是
文件名称
sub_title
string
200
是
下级标题
file_size
string
5
是
文件大小
file_path
string
5
是
文件路径
file_type
int
50
是
文件类型
is_slice
int
5
是
文件切片状态--
1/未切片 
2/切片中 
3/切片成功 
4/切片失败
is_delete
int
5
是
删除状态
f.响应示例：
{
    "total": 1,
    "type": "info",
    "error": null,
    "message": "文件列表",
    "data": [
        {
            "id": 25172,
            "project_id": 1783,
            "kb_id": 1675,
            "file_name": "公告第37号.pdf",
            "sub_title": "公告第37号",
            "file_size": "0.86MB",
            "file_path": "YH42YZQOAJSQK2PXGWIVN3QUKI/aico-rag/mashuang/kb_mashuang/公告第37号.pdf",
            "file_type": 1,
            "source": 1,
            "cr_user": "mashuang",
            "up_user": "mashuang",
            "is_slice": 3,
            "qa_status": 1,
            "abstract": "",
            "rec_question": "",
            "outline": "",
            "qa_schedule": -1,
            "is_state": 1,
            "is_delete": 0,
            "reserve1": "",
            "reserve2": "",
            "create_time": "2025-10-21T11:38:16",
            "update_time": "2025-10-21T14:07:39"
        }
    ],
    "start_time": 1761027000665,
    "end_time": 1761027000665,
    "err_code": 0,
    "page_index": 1,
    "page_size": 20
}
7.解析切片
a.接口调用URL:http://20.17.39.132:11105/aicoapi/knowledge_manage/file/split
b.请求方式：POST
c.请求参数：
字段
类型
长度
是否必填
描述
file_ids
list<int>

是
文件列表ID
kb_id
int
5
是
知识库ID
keep_img
int
5
否
是否保留图片
length
int
5
是
切分长度
overlap
int
5
是
重叠长度
pid
int
5
是
项目ID
type

int

1

是
切分类型--
1/长度切分  
2/目录切分
3/按照行 
4/按照列 
5/自动切分 
6/自定义切分（按照正则）
7/按照页切分
d.请求示例：
curl --location 'http://20.17.39.132:11105/aicoapi/knowledge_manage/file/split' \
--header 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOnsidXNlcm5hbWUiOiJtYXNodWFuZyIsInVzZXJfaWQiOiIxMDM0In0sImV4cCI6MTc2MzYwNjg5MX0.TMh344cwSmwOMyHD6VVggkqxyHOfWyH-5TGuMzRF7ZU' \
--header 'Content-Type: application/json' \
--data '{
    "user_id": 1034,
    "user_uuid": "cf11da521a134518855d92e129af2047",
    "pid": 1783,
    "file_ids": [
        25172
    ],
    "kb_id": "1675",
    "keep_img": true,
    "type": 1,
    "length": 512,
    "overlap": 100
}'
e.响应示例：
{
    "total": null,
    "type": "info",
    "error": null,
    "message": "切分中，请耐心等待！",
    "data": "",
    "start_time": 1761026829591,
    "end_time": 1761026829591,
    "err_code": 0,
    "page_index": null,
    "page_size": null
}

8.全量上线
a.接口调用URL:http://20.17.39.132:11105/aicoapi/knowledge_manage/knowledge/online
b.请求方式：POST
c.请求参数：
字段
类型
长度
是否必填
描述
id_list
list<int>

否
切片id列表
kb_id
int
5
是
知识库ID
pid
int
5
是
项目ID
d.请求示例：
curl --location 'http://20.17.39.132:11105/aicoapi/knowledge_manage/knowledge/online' \
--header 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOnsidXNlcm5hbWUiOiJtYXNodWFuZyIsInVzZXJfaWQiOiIxMDM0In0sImV4cCI6MTc2MzYyMDA4Nn0.8ddEP9qHQN6Iyp-zNybh45h9sX5I4P3hJhoF7CqSLYM' \
--header 'Content-Type: application/json' \
--data '{
    "kb_id": "1675",
    "pid": 1783,
    "id_list": []
}'

e.响应示例：
{
    "total": null,
    "type": "info",
    "error": null,
    "message": "完成",
    "data": "",
    "start_time": 1761028265447,
    "end_time": 1761028265447,
    "err_code": 0,
    "page_index": null,
    "page_size": null
}
