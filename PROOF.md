# 单台秩位门槛核证交班

白班按确切修订发行证据。夜班在源库关闭后接纳来件，按当班许可核定一枚标片的单侧门槛。次班按报告号核对当时采用的来件、许可和结论。V1 的登记、修订、单台秩位报告和初始化方式见 README.md。

## 调用约定

沿用 README.md 的两库初始化入口、连接所有权和外键设置。扩展初始化，使同一组调用也能在新库和已有 V1 库上使用下列入口。重复初始化保留既有记录。写入口接收无活动事务的连接。

| Python 入口 | 输入与返回值 |
| --- | --- |
| `evidence.seal.seal_proof(db, revision_id)` | 按源库确切修订发行并返回 `(text, local_certificates)`。`text` 是供交班的 V2 JSON 文本，`local_certificates` 是从核证标识到 `(较早原片号, 较晚原片号)` 的字典，仅台架留用。成功返回前同次保存正文和对照。 |
| `evidence.intake.accept_proof(db, text)` | 校验并固定 V2 来件，返回中心使用的文本接纳号。 |
| `analysis.rank_review.issue_proof(db, acceptance_id, marker, side, rank, allowed)` | 消费指定已接纳 V2 件并提交报告，返回下述报告字典。 |
| `reports.history.read_proof(db, report_id)` | 返回同形的已存字典，含原报告和回执。读取仅使用存值。 |

V2 接纳号和报告号为非空白可打印文本。`marker` 为来件的两枚具名标片之一。`side` 为 `at_least` 或 `at_most`，分别表示不早于或不晚于。`rank` 为从 1 到试片总数的整数，布尔非法。`allowed` 为可空的列表或元组，每项是一个不同的本件核证标识。报告保留请求中的许可顺序。确切修订号沿用 `get_revision` 的输入及错误语义。

## 证据与判读

V2 件的外层是 JSON 对象，字段为 `version`、`piece_id`、`batch_id`、`tray_id`、`revision_id`、`markers`、`specimen_count`、`certificate_ids`、`evidence`。`version` 为整数 2，`markers` 为修订的两枚具名标片，`specimen_count` 包括所有在册片。沿用 V1 的件号、批次、台架及修订身份规则。`certificate_ids` 为互异的非空白可打印文本标识列表，也是台架对照字典的完整键集。`evidence` 的 JSON 表示由实现确定并简述，须能在不访问源库时回答下述请求。

每条去重后的人工核证都对应一个本件标识，包括同时有读数推导的关系。核证标识仅在所属件上有效，独立发行的另一件使用各自的标识。原读数、普通片原编号和台架对照仅留源库。离线材料必须保留事后许可所需的证据效力。

设采用的核证清单是 `allowed` 的一个子集。每个相容顺序都是排完该修订全部在册片的一种顺序，须同时满足原修订的全部读数推导先后与采用的人工核证。读数推导按 V1 严格比较区间。只由未采用的人工核证支撑的先后不产生约束，同一先后若同时由读数推导仍有效。含传递关系，同一片在每个顺序中只出现一次，孤立片也计入秩位。

门槛须在采用该清单后每一种相容顺序中均成立，等于所给秩位也算达到门槛。签出条数最少的充分清单，并列任选。读数本身已足够时签出 `[]`。全部获准核证也无法保证时照常签发 `impossible`。允许全量重算及枚举核证子集。

## 接纳及报告

接纳校验外层身份、版本及字段类型，并校验所用证据格式及其内部引用。JSON 对象键重复、坏件或传入 V1 件报 `ValueError`。同件号同内容重投返回原接纳号，JSON 空白和对象键顺序不影响重投。同件号异内容报 `ValueError`。

`issue_proof` 和 `read_proof` 返回以下字段的字典。

| 字段 | 值 |
| --- | --- |
| `report_id`、`acceptance_id`、`piece_id` | 正式报告号、所用接纳号、所用来件号 |
| `origin` | 包含原件的 `batch_id`、`tray_id`、`revision_id` 的字典 |
| `marker`、`side`、`rank`、`allowed` | 原签发请求，`allowed` 保存为列表 |
| `status`、`certificates` | `proved` 与选中的标识列表，或 `impossible` 与 `None` |
| `receipt` | 包含同一 `report_id` 和非空文本 `receipt_id` 的字典 |

非法请求及传入 V1 接纳号报 `ValueError`。格式合法的未知 V2 接纳号或报告号报 `KeyError`。发行、接纳与签发的写入失败由调用方收到异常，失败的调用无新增且可重试。签发的正文和回执同次提交。源账追加勘误、修改调用者持有的请求或结果对象、关闭并重开中心库后，按原号领取的存值及回执保持一致。旧件、旧历史和全部 V1 接口与编码继续可用。

## 样例及核验

`samples/proof_cases.py` 的 `record_cases(source)` 用原登记和修订入口准备数据，返回样例名到确切修订号的字典。`python3 -B -m samples.proof_cases` 可在初始工程中复核这些修订的 V1 边际。交付后可对这些修订调用 `seal_proof`。用发行返回的台架对照取得下面具名关系对应的实际核证标识，再关闭源库，只向中心传正文。

| 修订 | 夜班请求与预期 |
| --- | --- |
| `manual-chain` | B 的 V1 边际为 `[3,4]`。请求 B `at_least` 3，允许全部时须用 A→local-x 和 local-x→B，少许可其中一条即 `impossible`。请求 A `at_most` 2 同样须用两条。 |
| `reading-chain` | B 的 V1 边际同为 `[3,4]`。请求 B `at_least` 3，许可为空，签 `proved` 与 `[]`。 |
| `dual-source` | local-x→B 同时出现在读数推导和人工核证中，重复录入的核证只拿到一个标识。请求 B `at_least` 3，即使许可为空也签 `proved` 与 `[]`。 |
| `alternative` | 请求 B `at_least` 3。全部许可时唯一最少清单为 local-u→B。只许可 local-x→B 与 local-y→B 时须同时采用两条。只许可 local-x→B 时签 `impossible`。全部许可也不能保证 B `at_least` 5。 |

沿用 `.pointwise-runtime.json`。现有清单的 `verify` 和 `demo` 都是直接运行的 argv 数组，`setup` 是准备命令的 argv 数组列表。将新旧核验接入 `verify`，核验不符时返回非零退出码。`demo` 展示实际断源裁决及勘误后重开中心库的领取结果，原 V1 演示入口继续可用。
