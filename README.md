信息

支持excel直接导入和手动加学生/老师信息

学生：序号	姓名	性别	年级	科目	家庭情况与学习情况（薄弱学科、具体知识短板、（学习风格（视觉型/听觉型/动手型）、兴趣爱好、性格特点）	社工姓名	社工联系电话	是否优先 特殊需求	

老师：序号 姓名 性别 学号 学邮 院系（专业） 辅导方式线上线下 匹配需求（预匹配还是直接匹配） 之前是否参加过 个人性格和风格（耐心吗，活泼吗，严肃吗） 对性别的要求  
偏好学生的科目（1位，2位，3位） 学段（1位，2位，3位）   



打分阶段

我的想法是，对每一对合法的师生对进行打分。首先什么是合法：性别和线上线下这两个强制要求会过滤掉不合法师生对，剩下的都是合法。然后每一对师生的打分维度有年级偏好匹配度（如果学生的年级和志愿者的第一顺位匹配，则3分，第二顺位2分，第三1分，不是则0分）/科目需求匹配度（如果学生的科目需求与志愿者的第一顺位匹配，则3分，第二2分，第三1分，不是则0分）（这里的分数设置目前是拍脑袋的，可以后期实验调整）/学习风格、性格与教学风格匹配度/志愿者专业与学生情况匹配程度/特殊需求匹配度。后两个维度目前也是拍脑袋的，我目前考虑设计打分表之后调用api来打分。

目前的想法是用struct存师生信息，然后n*m遍历，存储每个合法对。之后遍历合法对，通过调用deepseekapi的方式对主观维度打分，通过公式计算每一对的最终分数并存储。


匹配阶段
从匹配度高到低进行匹配。如果当前的匹配对中，小朋友是优先匹配的，那么选择该对，并在师生集合中分别把两人都删掉，并把这一对在排序中删掉。如果当前的匹配对中，小朋友或者老师已经不在师生集合，那么把这一对删掉。以这个规则对所有匹配对进行遍历。

遍历一遍之后，如果仍然剩余匹配对，那么继续从高到低进行匹配，这次都不是优先匹配了。对于当前的匹配对，选择该对，并在师生集合中分别把两人都删掉，并把这一对在排序中删掉。如果当前的匹配对中，小朋友或者老师已经不在师生集合，那么把这一对删掉。以这个规则对所有匹配对进行遍历。

第二次遍历之后这个匹配对的大根堆就空了。


打分-匹配流程，先对直接匹配的老师做。
如果还有剩下的学生，那么对剩下的学生和预匹配的老师做打分-匹配。


浏览器请求被拦住了


基础分这里我给你说明一下思路。我们先分为4部分，其中3部分构成总分100分，权重可以调整，先定grade-20分，subject-40分，教学风格（）-40分，然后特殊需求总分20分，在100分之外，对不符合特殊需求的匹配对进行扣除，如果没有特殊需求就视为0。然后，grade，按照符合的程度分别给100%，66.7%，33.3%的分数；subject，给老师的优先级从高到低负分3/2/1，学生赋分3/2/1，然后对于每一学科进行计算，公式是老师优先级分数*学生优先级分数，这样最高9分，最低0分，我们对subject这里的40分分成9份给分。然后教学风格和特殊需求的具体评分标准咱们空着，后面deepseek做。

启动方式：
for windows
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload

In 2nd cmd:
python -m http.server 5500

wsl指令略用不同，参阅AI.

http://127.0.0.1:5500/students.html
http://127.0.0.1:5500/volunteers.html
http://127.0.0.1:5500/matching.html

0221更新：改正预览上传数据的bug，优化了student和volunteer图形界面。建议之后的match算法直接从数据库db寻找数据，然后完成接下来的算法，可以输出match之后的excel.等算法完成后继续优化match的网页界面。参考db中的字段更改：
STUDENT_COLUMNS = [
    "seq_no", "name", "gender", "grade_stage", "mode",
    "subj1", "subj2", "subj3",
    "weakness_text", "learning_style", "interests_text", "personality_text",
    "social_worker_name", "social_worker_phone", "is_priority", "special_needs_text",
]

VOLUNTEER_COLUMNS = [
    "seq_no", "name", "gender", "student_no", "email", "department_major",
    "mode", "match_mode", "gender_requirement",  # gender_requirement 保留
    "grade1", "grade2", "grade3",
    "subj1", "subj2", "subj3",
    "capacity", "style_text",  # 改为 style_text 而不是 teaching_style_text
    "has_participated_before",  # 改为 has_participated_before 而不是 participated_before
]
之后下学期我问卷收集也要按这些字段来，否则会报错。新增删除功能，解决重复导入冲突问题。
