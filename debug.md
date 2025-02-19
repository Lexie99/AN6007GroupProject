**1. To do:**
    录demo
    （清除redis当前数据库数据命令行：redis-cli FLUSHDB）

**2. 准备相应的documents：**
A documentation (or documents) containing:
a. Job distribution and contribution within group members
b. The project milestones, the completion status, any issues and recommendations to improvements
c. API definitions
d. Batch Jobs features and illustrations
e. Generative AI consultations Logs:
    i. The need
    ii. The original codes
    iii. The suggested codes from generative AI platform
    iv. The final amendments and adopted codes with learning take-aways

**3. 准备pre：**

    In your presentation, you are required to demo your solutions and focus on explaining:

    1. how and why, you have selected on the data structure that will support this business case.  
    2. the choice of visualization  
    3. how you prepare the test data to ensure your solution is working fine.  
    4. how you prepare the log to support the solution needed of server restart  
    5. how you prepare the repetition of monthly electricity consumption for billing  

    You should illustrate that your solution works.

    You also required to share the challenges you encountered and how you overcome the issues.  
    The duration of the presentation should not be more than 8 - 12 mins per group (or 2 mins per person).  
    You are advised to adhere to the time limit strictly.

    Please note that if you are not able to complete the entire assignment, you are still required to share your assignment journey as it is graded separately from the final outcome. Each of you are required to take part in the presentation, with appropriate presentation materials or illustrations. You are advised NOT to read out from scripts while presenting.

**4. possible improvements：**
    1.日志与备份的恢复支持
        目前系统的日志和备份功能仅用于记录和追踪操作，但并没有实现数据恢复功能。
        由于恢复逻辑较为复杂，未来可以考虑设计一个自动或半自动的恢复流程，使系统在服务器重启或故障后，能够从备份日志中还原关键数据，保证业务连续性。
    2.持久化存储方案的完善
        当前 Redis 作为内存数据库，在重启后数据会丢失。
        为了避免这种情况，应结合 Redis 的持久化配置，比如 RDB 快照和 AOF 日志，使数据在重启后能恢复到最新状态，确保数据的安全性和可靠性。
    3.前后端分离的进一步优化
        在 dash.register 前端模块中，为了实现区域下拉选项根据所选 region 自动更新，我们在前端中直接引入了 AppConfig。
        这种做法在一定程度上违背了前后端完全分离的原则。未来可以将这些配置信息通过 API 提供给前端，前端只负责展示数据和交互逻辑，从而实现真正的前后端分离。
    4.电表读数数据异常的检测与校验机制
        目前对于电表上报的数据，系统尚未实现充分的异常检测，比如：
            同一时间戳的重复数据；
            异常的电量消费（例如突然出现过大的增量）；
            读数缺失等情况。
        未来可以加强数据校验逻辑，对每条上报数据进行更严格的检查，并设计相应的异常处理和报警机制，确保数据的准确性和完整性。
    