# 材料质控室单台秩位交班 V1

白班登记同批的两枚参考标片和各台清册。台架员提交完整读数和已经核实的先后关系，交班员为指定修订发行单台件。夜班在台架断开后接纳交班件，按标片签发可达秩位范围。试验负责人和下一班可凭正式报告号领取原结论和回执。

## 运行

需要 Python 3.11。所有依赖均来自标准库。在项目根目录运行完整回归和业务样例。

```sh
python3 -B check_project.py
python3 -B -m samples.demo
```

控制台物化时提供 `check_project.py`。也可直接使用标准发现命令 `python3 -B -m unittest discover -s tests -t . -p 'test_*.py'`。

样例使用两份夹具和相互独立的源库、中心库路径。四片台架的确证为 A 先于 x，x 先于 B，y 自由。将 y 插入三片链的四处位置，得到 A 为 `[1,2]`、B 为 `[3,4]`。三片台架没有严格先后，两枚标片均可占任意位置，范围均为 `[1,3]`。样例关闭源库后接纳和签发，再重开中心库领取。

## 调用

所有入口的 `db` 是调用者负责关闭的 SQLite 连接。使用标准 `sqlite3.connect`，在每次打开后执行 `PRAGMA foreign_keys = ON`。写入口接收无活动事务的连接并在返回前提交。使用 `initialize_panel`、`initialize_revisions`、`initialize_issued_pieces` 初始化源库。使用 `initialize_intake`、`initialize_reports` 初始化中心库。重复初始化保留已有业务记录。所有标识用非空白可打印文本表示，保留原字符。持久修订号、接纳号和报告号是各自库内的正整数，件号是跨源使用的文本标识。

| 模块和入口 | 输入与结果 |
| --- | --- |
| `panel.registry.register_panel(db, batch_id, markers, unit, tray_id, members)` | 传入两枚具名标片、批次单位和完整台架清册，返回 `(batch_id, tray_id)`。`read_roster(db, batch_id, tray_id)` 返回清册与批次定义。 |
| `bench.revisions.record_revision(db, batch_id, tray_id, observations, certificates=())` | 读值为 `(片号, 下界, 上界)` 行，核证为 `(较早片号, 较晚片号)` 行。返回 `RevisionSnapshot`。`bench.revision_store.get_revision(db, revision_id)` 读取指定快照。 |
| `evidence.seal.seal_v1(db, revision_id)` | 返回已提交的不可变 `V1Piece`。`evidence.issued_store.read_issued_v1(db, piece_id)` 读取已发行件。`evidence.codec.encode_v1(piece)` 将其编码为 JSON 文本。 |
| `evidence.intake.accept_v1(db, text)` | 返回 `AcceptanceReceipt`，包括中心接纳号、原件号和出处。`read_accepted_v1(db, acceptance_id)` 返回 `(piece, receipt)`。 |
| `analysis.rank_review.issue_v1(db, acceptance_id, marker)` | 按身份选取一枚标片，签发 `V1Report`。报告包含区间、所用接纳及件号、确切出处和回执。 |
| `reports.history.read_v1(db, report_id)` | 返回同形的已存报告及回执。读取可在重开以后进行。 |

清册必须含两枚不同标片且台内所有片号唯一。同批两台可以使用相同普通片号。标片对及成员按身份规范排序，与输入顺序无关。同内容重复登记返回原标识。同批单位或标片定义与原登记冲突、同台成员冲突、缺少标片或片号重复均报 `ValueError`。

每枚在册片恰有一行读数。端点可为整数、`Fraction` 或可由 `Fraction` 精确解析的文本，例如 `1/3` 与 `0.125`。空端点、布尔、浮点和倒置区间报 `ValueError`。有理数在源库以既约整数分子和正分母保存。区间按同一单位从小到大比较。只有上界严格低于另一片下界才推导先后。相接与重叠可以另有人工核证。重复同向证据只计一条边，显式核证端点必须在册，全部证据合并后须无环。非法勘误保留已有修订，合法勘误追加新修订。

读数和普通片号保留于源库。V1 件的字段为 `version`、`piece_id`、`batch_id`、`tray_id`、`revision_id`、`markers`、`specimen_count` 和 `rank_bounds`。每枚标片的范围由传递先后决定，一基最早位为严格祖先数加一，最晚位为试片总数减严格后继数。孤立试片也计入总数。中心按完整规范化内容接纳，编码空白及对象键顺序无关。同号异内容、非法字段和越界区间报 `ValueError`。选用非本件标片也报 `ValueError`。未知台架、确切修订、发行件、接纳或报告按原查询入口报 `KeyError`。SQLite 提交错误会传给调用方。发行失败无新件，报告失败时正文与回执均无新增，原输入可重试。勘误后签发的报告与已签发报告各有固定出处。
