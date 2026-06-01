2026 卓越杯 数星阁支持系统

数星阁是复旦大学数学学院的支教志愿服务团队，组织大学生为中小学生提供线上线下的一对一志愿教学。需根据师生的科目偏好、年级篇好、性格特点、教学风格等信息进行志愿者匹配。基于这一需求，我们设计了师生匹配算法，结合llm调用，可以高效完成师生一对一匹配任务。并开发前端进行可视化操作和数星阁团队展示。

0225更新：
完成完整匹配系统的开发，包括调用Deepseek和匹配算法的细节。下面进行说明：

根目录下更新了“数星阁支持系统开发书”，师生匹配系统的全部开发细节在文件中均有说明。这个文件包含了系统设计的全部思路，包括数据字段、打分规则、系统功能边界确定等等。后面修改的同学可以先花一点点时间详细阅读一下，具体思路细节全部在里面。如果觉得繁琐也没关系，如果后续希望借助AI继续开发，那么可以直接把这个文件+开发记录里的文件树复制给AI，它会明白咱们在做什么，这样应该是提高效率的。

根目录下建立table文件夹，存放的是志愿者和学生表格。其中“volunteer-smoke”和“student-smoke”是写好的两个完整的、可以适配系统的示例，我已经将他们落库，也就是说现在后端app.db存放的就是这5个学生、5个志愿者的信息和匹配结果。其中“volunteer”和“student”两个xlsx文件是我目前做了一半的完整表格的适配版本。具体每个字段的含义是什么、如何理解系统适配的表格，可以参考开发书，也可以参考“students_template_v2”和“volunteers_template_v2”这两个文件的表头。

前后端目录下分别进行了这两部分的代码更新。如果你想要完整尝试“导入数据-落库-匹配”的流程，在后端运行时需要开一下虚拟环境，安装requirements里面的所有依赖，然后配一个Deepseek的密钥。具体的操作如下（操作系统不同的话可能会有小修改，那么你可以把下面的命令语句发给AI，让它帮你改一改就ok）：

    #建立虚拟环境并激活：
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1

    #安装依赖
    cd .\backend
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    python -m pip install "httpx<0.28" # httpx要做一个降级，过后我可以改一下requirements

    #配api密钥
    $env:DEEPSEEK_API_KEY = "" #也可以改成你自己的deepseek密钥
    echo $env:DEEPSEEK_API_KEY #检查下配好了没有

    #启用后端
    python -m uvicorn main:app --host 127.0.0.1 --port 8000

    #新开一个窗口启用前端
    cd frontend
    python -m http.server 5500

然后可以打开后端：http://127.0.0.1:8000/docs
访问前端：
学生管理：http://127.0.0.1:5500/students.html
志愿者管理：http://127.0.0.1:5500/volunteers.html
匹配与结果：http://127.0.0.1:5500/matching.html

之后就可以进行测试了~现在我落库的是两个smoke文档里面的少量学生和老师，目前看上去是ok的，大家可以自己上传测试，然后有什么问题可以和我讲。如果想测试新的数据，把现在的app.db删掉就好。

后续可以解决的问题：
1、5个学生*5个老师的匹配花了5分钟左右，这里也许可以优化。好的地方是调ds的成本还是挺低的，这个规模的数据大概花了3分钱。
2、大文档里的数据还要继续改成适配系统的模式。
3、页面优化。（前端保留了一些ai的碎碎念）（我现在可以保证前端的接口后面不会有大变化了，所以大家可以放心做页面设计了）
4、调用API的prompt优化




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




