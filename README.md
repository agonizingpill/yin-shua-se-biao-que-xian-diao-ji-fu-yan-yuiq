# 铅叶印务 · 印刷色标缺陷与调机复验

四色密度与网点扩大率驱动缺陷判读，贯通首张、调机、执行、复验和主管签印。

模拟客户：铅叶印务22人四色胶印班。过去机长凭肉眼判色、在纸单记录调机，乳化和偏色处置混淆；不同开机单样张混用；机器刚调整就恢复量产，复验和责任签印缺失。本项目接收密度计色标读数，替代判读与调机闭环核对，下游是主管确认的量产开机单。

## 多模块流程

- PrintJob开机单：编号、印件、纸张、目标密度、setup/adjusting/production/hold状态；已有判读/调机后规格冻结。
- ProofSheet色标：四色密度、网点扩大率、工单外键、真实缺陷/概率/分类证据。未关联色标可校正并清除旧判读，已作为调机首张或签印复验张则冻结。
- 缺陷判读：Python worker以StandardScaler+RBF SVM区分合格/乳化/偏色，当前送测样不进入参考训练。页面显示概率和30张留出混淆矩阵。
- Adjustment调机与复验：乳化默认供水−8%、偏色默认供墨−6%；待执行可在规则范围内修订，执行后指令冻结。主管签印要求已执行、不同于首张的同工单合格复验，且复验判读晚于执行。成功同时闭合Adjustment、关联reproof_id、PrintJob进入production。

## 快速启动

```sh
cp .env.example .env
docker compose config --quiet
docker compose up -d --build
docker compose exec -T backend python -m scripts.seed_demo
```

[工作台](http://localhost:18229)，[API文档](http://localhost:19229/docs)，MySQL端口17729。

|账号|口令|角色|权限|
|---|---|---|---|
|admin@qianye.demo|Press2026!|admin 印刷主管|全部操作，最终签印|
|pressman@qianye.demo|Press2026!|pressman 机长|工单/色标录入、判读、指令、执行；不能签印|
|viewer@qianye.demo|Press2026!|viewer 观察员|六页只读|

JWT8小时；密码PBKDF2-SHA256盐化；本地演示部署前修改JWT_SECRET和数据库口令。

## 一天剧本

1. 08:30 打开PJ-26091画册封套，157g哑粉纸、目标密度1.40。
2. 09:00 核对PS-FIRST：C1.02/M1.04/Y1.00/K1.05，网点扩大28%。
3. 09:30 后台读取首张，SVM判为乳化，生成减供水8%的调机单。
4. 10:00 机长可在待执行时修成减供水7%，乳化指令不能改成增水。
5. 10:30 先登记印版、测量套准并主管认可就绪，再登记调机执行，首张与执行指令冻结；此时不能用执行前的旧合格判读签印。
6. 11:00 不合格PS-FAIL与跨工单PS-OTHER作为异常分支均被拒绝。
7. 14:00 重新读取同工单PS-RECHECK（约1.40四色密度，扩大14%）为合格，主管签印。
8. 16:00 工单production、Adjustment signed、reproof_id关联一致，观察员查询闭合依据。第二工单PJ-26092演练偏色供墨调整。

## 真算与验证口径

独立ReferenceSheet150张模拟标签色标，每类50张；送测ProofSheet从不插入参考。按标签分层固定seed42拆为120训练/30留出，StandardScaler仅训练fit，SVC(kernel=rbf,C=2,probability=True,random_state=42)只训练拟合，输出当前样张predict/proba及留出accuracy、固定类别顺序混淆矩阵。密度除以本工单target_density，网点扩大除100；参考密度按1.4标准归一化。概率仅为模型倾向，不替代执行后的现场复验。参考数据固定seed生成，可复现但不代表真实生产准确率。

worker通过Redis取proof_id，结果持久化ProofSheet，另写backend/worker共享卷`/artifacts/proof-<id>.json`。证据包含参考/留出编号，能证明训练与验证互斥以及当前色标不入训练。参考少于60张判读失败。

## 工程与本地开发

|层|实现|
|---|---|
|前端|原生HTML/CSS/JS ES modules、Nginx1.27|
|后端|Python3.12 FastAPI、SQLAlchemy、JWT|
|算法|scikit-learn1.6.1、NumPy、Redis worker|
|持久化|MySQL8、Redis7 AOF、共享计算卷|

五服务frontend/backend/worker/db/redis健康检查齐全。MySQL用TCP业务账号SELECT1，worker心跳，frontend依赖backend健康。Nginx/api去掉前缀代理。环境变量与端口在.env.example，专用子网10.221.30.0/24可改为本机空闲子网，SEED_DEMO启动自动补演示数据。seed自然键仅增缺失，保留用户修改。

backend/src/models.py三个实体+参考/User/Audit；schemas.py输入；services.py冻结/调机/签印规则；classifier.py训练与验证；worker.py真实计算；main.py权限路由；auth.py认证；middlewares.py请求ID/限流。frontend/src/pages/jobs/proofs/diagnosis/adjustments.js及plates/samples.js对应六页；api.js客户端、store.js状态、components/press.js色标条/状态/选择器跨页共用、utils/format.js数字/转义/表单工具。

角色、缺陷、工单和指令状态在backend/src/constants.py与frontend/src/constants.js；后端执行所有权限与状态约束，页面按钮禁用作提示；完整性异常返回可恢复409。

本地设置DATABASE_URL/REDIS_URL，安装backend/requirements.txt，在backend目录运行`uvicorn src.main:app --reload`与`python -m src.worker`，前端建议使用Compose代理。停止保留数据`docker compose down`，验收清理`down -v --remove-orphans`。测试/截图/日志在`../../test-artifacts/gb-1030/`。

已知范围：模拟色标可分性较强，留出高准确率不代表真实印刷；单机工单流程，已扩展量产抽检及停复机；未实现撤销历史签印或多轮缺陷合并。执行后的判读时间用于复验时序，没有接入硬件取样防伪。worker故障无可靠作业重投。Google字体离线回退。License MIT。


## 印版版本与量产停复机扩展

**印版上机核对**：PlateSet关联工单，版本号在工单内唯一，记录客户定稿来源、最大套准误差与主管。`registered→measured→ready`；套准误差>0.15mm拒绝认可，就绪后测量和来源冻结，重制另建新版本。当前有效印版为最新登记版本，未就绪时新增调机执行、主管签印及量产抽检均拒绝；原已签印记录不回写。

**量产抽检停复机**：PressSample保存工单、真实新ProofSheet、印版外键/就绪快照、递增抽检序号及已印数量。专门接口创建新色标并交Redis/Python worker分类，保持通用接口对已签印旧色标的冻结。合格样`passed`；不合格或判读失败为`held`，生成PressHold并将工单置`hold`，阻止继续抽检。停机复验专门接口再次新建同工单ProofSheet，不允许复用签印前旧色标，所有复验ID保留历史。复验不合格继续停机，合格且主管附排查依据关闭停机后才恢复`production`；重复复机拒绝。

新增接口：`GET/POST /plates`、`POST /plates/{id}/measure`、`POST /plates/{id}/approve`（仅主管）；`GET/POST /press-samples`、`GET /press-holds`、`POST /press-holds/{id}/recheck`、`POST /press-holds/{id}/close`（仅主管）。机长可登记印版/测量/抽检/新复验，观察员只读。页面为`pages/plates.js`与`pages/samples.js`；后端`production_models/production_schemas/production_routes/plate_service/sampling_service`，原services/main/worker接入就绪守卫与分类后停机。

Seed为两个工单各补一套V1待测印版，不自动伪造已就绪版本或量产抽检；工单2、色标5、参考150保持原基础规模。新3表自动补建，无旧表列变更，已有签印与判读证据保留。重复seed保留人工纸张修改、版次、抽检和停机处置。

续篇剧本：登记V-BROWSER→实测0.08mm→主管认可；已签印量产工单抽第4张检查点，新的PS-BROWSER-RUN-BAD判乳化→自动停机→专门表单录PS-BROWSER-HOLD-GOOD四色1.40/扩大14%→worker判合格→主管记录减供水依据并复机。样张保留当时印版快照，旧签印张仍冻结。真实验收与4张新增1440×900截图见`test-artifacts/gb-1030/expansion/`。

范围：抽检数量和色标为人工录入，停机状态作用于本应用后续操作，不直接控制真实印刷机；不包含PLC联锁、物理取样防伪、撤销历史签印或可靠作业自动重投。固定模拟参考的高留出准确率不能作为真实生产效果承诺。


## V3 纸张、点检与成品交付

保留原六页并新增纸张上机领退、印机开机点检、装箱发货交接三页，共九业务页面，原量产抽检和停机新复验表单仍可操作。

纸张批次PaperLot按g/m²与工单paper中的数字g匹配，active批次整笔扣库建立PaperIssue，隔离/不足/克重不符拒绝；已有领纸后工单paper冻结。每次PressSample.quantity表示“截至本次累计已印张数”，不将历次累计读数相加；新读数不能小于历史最高累计量，不能超过净领纸。PaperIssue可一次受控退回未用余纸，退后净领纸须≥历史最高已印量，不能退已经印刷的纸。历史样张与签印不修改，新操作校验现有累计基线。

PressMachine有ready/maintenance，PressInspection绑定工单/印机和日期、润滑、防护。草稿可补正日期及检查项，主管仅认可今日、润滑及防护均完成、机器就绪的点检；认可后冻结。新调机execute及量产sample使用最新一条点检，该记录须今日approved，不能跳过新draft沿用旧认可；保养中的印机拒绝新execute/sample。种子不伪造认可，历史signed保留。

PrintPack箱码唯一，open可取消；production且无活动Hold/待判读样时封箱，已封及已发累计张数≤最后合格抽检累计量与净领纸。seal保存色标/印版/数量快照，封后数量冻结。PrintShipment由机长选择同工单已封未占用箱建立草稿，ShipmentPack.pack_id唯一防重复出库；主管装运时复核当前量产质量、冻结客户/物流/箱单/合格样/净纸快照，客户签收人留凭；重复装运/签收、跨工单混箱、停机或待判读发货拒绝。

三角色可GET新增列表；机长/主管可入库、领退纸、草稿点检、装箱封箱/取消、建发货单和签收；主管专属纸张隔离、印机登记/保养、点检认可及发货装运，viewer只读。主要API：/paper-lots、/paper-issues及return；/press-machines、/press-inspections及PUT/approve；/print-packs及seal/cancel；/print-shipments及dispatch/receive。

按父工单锁串行化领退纸、累计印量、封箱和装运；锁读populate_existing刷新身份缓存。MySQL使用READ COMMITTED，取得工单锁后的聚合读取已提交净领纸/封箱量，避免等待前快照导致超额。种子仅缺失时添加157g/128g批次和PRESS-04，保留人工库存、历史signed与发货快照。

本演示按张数追溯，不接真实WMS/物流，也不估算裁切、调机废纸；生产累计读数和现场可退余纸由机长录入，系统约束上限及一次退回。原240次/分钟限流仍生效。真实v3证据保存在test-artifacts/gb-1030/v3/。
