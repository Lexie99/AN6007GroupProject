**1. To do:**
    测试
    讲解
    

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
    1.目前的日志和备份仅用作记录，暂时没有restore的功能（因为restore的逻辑太复杂了）
    2.目前数据只用redis存在memory里，一旦redis服务器有问题，所有数据都会丢失，长久化储存和数据恢复还是需要存入本地磁盘，不能只使用memory
    3.没有做到完全的前后端分离，dash.register中，为了用户注册时area下拉项能够根据选择的region自动更新，引入了AppConfig