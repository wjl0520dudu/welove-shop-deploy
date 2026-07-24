# 多模态商品检索实验 v1：待补充 35 条图片清单

本清单与 `datasets/multimodal_retrieval_v1.jsonl` 的 15 条 Golden 冻结样本共同组成 50 条主评测集。

每一条补充完成后，需要记录：公网可访问的 `query_image_url`、用户查询文本、至少一个强相关商品 ID（grade=2）；符合大类但不完全符合约束的商品可标为 grade=1。不要使用商品详情页截图、带大面积文字水印的海报或无法公开访问的图片。

建议统一上传到 OSS 前缀 `eval-test-images/multimodal-retrieval-v1/`。下表的“OSS 文件名”是固定映射；图片格式统一使用 `.jpg`。

| ID | OSS 文件名 |
|---|---|
| new-001 | `new-001-sensitive-skin-cleanser.jpg` |
| new-002 | `new-002-anti-aging-serum.jpg` |
| new-003 | `new-003-oil-control-setting-powder.jpg` |
| new-004 | `new-004-waterproof-trail-shoes.jpg` |
| new-005 | `new-005-basketball-shoes.jpg` |
| new-006 | `new-006-mens-sports-shorts.jpg` |
| new-007 | `new-007-lightweight-laptop.jpg` |
| new-008 | `new-008-flagship-smartphone.jpg` |
| new-009 | `new-009-noise-cancelling-headphones.jpg` |
| new-010 | `new-010-unsweetened-black-coffee.jpg` |
| new-011 | `new-011-breakfast-milk.jpg` |
| new-012 | `new-012-healthy-nut-snack.jpg` |
| new-013 | `new-013-sensitive-sunscreen.jpg` |
| new-014 | `new-014-lightweight-face-cream.jpg` |
| new-015 | `new-015-commuter-lipstick.jpg` |
| new-016 | `new-016-mens-daily-running-shoes.jpg` |
| new-017 | `new-017-womens-waterproof-hiking-shoes.jpg` |
| new-018 | `new-018-mens-quick-dry-tshirt.jpg` |
| new-019 | `new-019-study-tablet.jpg` |
| new-020 | `new-020-camera-flagship-android-phone.jpg` |
| new-021 | `new-021-commuter-wireless-earbuds.jpg` |
| new-022 | `new-022-instant-noodles.jpg` |
| new-023 | `new-023-zero-sugar-sparkling-water.jpg` |
| new-024 | `new-024-mild-coffee.jpg` |
| new-025 | `new-025-skincare-gift-set.jpg` |
| new-026 | `new-026-running-shoes-outfit.jpg` |
| new-027 | `new-027-sports-shorts-outfit.jpg` |
| new-028 | `new-028-tablet-study-accessory.jpg` |
| new-029 | `new-029-coffee-afternoon-snack.jpg` |
| new-030 | `new-030-sunscreen-cleanser-pairing.jpg` |
| new-031 | `new-031-sneaker-running-cap-pairing.jpg` |
| new-032 | `new-032-dark-running-shoes.jpg` |
| new-033 | `new-033-multi-object-earbuds.jpg` |
| new-034 | `new-034-partial-sunscreen-tube.jpg` |
| new-035 | `new-035-blurry-basketball-shoes.jpg` |

## A. 图搜同类 / 相似款（12 条）

| ID | 要找的图片 | 建议查询文本 | 标注重点 |
|---|---|---|---|
| new-001 | 白色瓶身、泵头的温和洁面乳实拍 | 按图找适合敏感肌的洁面 | 洁面、温和/敏感肌 |
| new-002 | 滴管玻璃瓶的抗初老精华 | 找图中这类抗初老精华 | 精华、抗初老 |
| new-003 | 罐装散粉或粉饼，最好能看出粉扑 | 找类似的控油定妆产品 | 散粉/粉饼、控油 |
| new-004 | 一双越野跑鞋，鞋底花纹清晰 | 按图找防水徒步或越野鞋 | 徒步鞋/越野鞋 |
| new-005 | 篮球鞋侧面实拍，避免品牌 Logo 过于突出 | 找和图里类似的实战篮球鞋 | 篮球鞋 |
| new-006 | 运动短裤平铺或上身图 | 找同类男士运动短裤 | 运动短裤 |
| new-007 | 轻薄笔记本电脑打开状态 | 找类似的轻薄办公笔记本 | 笔记本电脑 |
| new-008 | 智能手机背面实拍，突出多摄像头 | 找图中同类型旗舰手机 | 智能手机 |
| new-009 | 头戴式降噪耳机 | 找类似的降噪耳机 | 耳机；若语料没有头戴式，改为真无线耳机图片 |
| new-010 | 玻璃瓶装冷萃/黑咖啡 | 按图找无糖黑咖啡 | 咖啡、无糖 |
| new-011 | 牛奶或高蛋白奶盒装图 | 找类似的早餐牛奶 | 牛奶 |
| new-012 | 袋装坚果或低糖零食 | 找类似的健康零食 | 零食、低糖/坚果 |

## B. 图 + 硬约束（13 条）

| ID | 要找的图片 | 建议查询文本 | 必须验证的约束 |
|---|---|---|---|
| new-013 | 防晒霜瓶/管装 | 按图找敏感肌可用、200 元以内的防晒 | 防晒 + 敏感肌 + 价格 |
| new-014 | 舒缓修护面霜罐装 | 找类似面霜，敏感肌换季用 | 面霜 + 敏感肌修护 |
| new-015 | 口红试色或口红管 | 找类似色系的通勤口红，150 元以内 | 口红 + 价格 |
| new-016 | 跑鞋 | 找同类跑鞋，男士、适合日常慢跑、1000 元内 | 跑鞋 + 人群 + 场景 + 价格 |
| new-017 | 徒步鞋 | 按图找防水徒步鞋 | 徒步鞋 + 防水 |
| new-018 | 运动 T 恤 | 找相似的速干男士 T 恤，200 元内 | T 恤 + 速干 + 价格 |
| new-019 | 平板电脑 | 图里这种平板，预算 4000 左右，适合记笔记 | 平板 + 价格 + 学习场景 |
| new-020 | 手机 | 找类似的安卓手机，拍照好、6000 元以内 | 手机 + 拍照 + 价格 |
| new-021 | 真无线耳机 | 按图找降噪强、适合通勤的耳机，2000 内 | 耳机 + 降噪 + 价格 |
| new-022 | 即食方便面 | 找同类方便面，适合宿舍囤货 | 方便食品 + 场景 |
| new-023 | 气泡水 | 找类似饮料，要 0 糖 0 脂 | 饮料 + 0糖0脂 |
| new-024 | 咖啡杯或咖啡包装 | 找类似咖啡，晚上喝也不想太苦 | 咖啡 + 口味偏好 |
| new-025 | 护肤礼盒 | 图里这类护肤品，送 25 岁女生，推荐一款抗初老精华 | 抗初老精华 |

## C. 图文语义互补 / 跨类搭配（6 条）

| ID | 要找的图片 | 建议查询文本 | 标注目标 |
|---|---|---|---|
| new-026 | 跑鞋 | 给图里跑鞋搭一件夏季速干上衣 | 主要相关商品应为运动 T 恤，不是跑鞋 |
| new-027 | 运动短裤 | 给这条短裤配一双日常跑步鞋 | 主要相关商品应为跑鞋 |
| new-028 | 平板电脑 | 图里平板配一个适合学习的无线耳机 | 主要相关商品应为耳机 |
| new-029 | 咖啡 | 给这杯咖啡搭一个下午茶低糖零食 | 主要相关商品应为零食 |
| new-030 | 防晒霜 | 图里是防晒，搭一款适合油皮的洁面 | 主要相关商品应为洁面 |
| new-031 | 男士运动鞋 | 搭配一顶适合跑步的棒球帽 | 主要相关商品应为帽子 |

## D. 边界与鲁棒性（4 条）

| ID | 要找的图片 | 建议查询文本 | 通过标准 |
|---|---|---|---|
| new-032 | 同一款跑鞋在偏暗光线下的实拍 | 这双鞋类似什么跑鞋 | 仍至少召回一个 grade=2 跑鞋 |
| new-033 | 一张画面里有耳机、手机和咖啡三种物品 | 找图里的无线耳机 | 以文本明确指定的耳机为主，避免被其他物体干扰 |
| new-034 | 商品仅露出局部，例如防晒管的半截 | 找类似的防晒，清爽不油腻 | 仍可召回防晒；记录图片裁切情况 |
| new-035 | 一张模糊的篮球鞋远景 | 找同类篮球鞋 | 至少一款 grade=2 篮球鞋进入 Top10；单独观察低清退化 |

## 交付格式

每条完成后追加到 `datasets/multimodal_retrieval_v1.jsonl`：

```json
{"query_id":"new-001","query_text":"按图找适合敏感肌的洁面","query_image_url":"https://你的公开图片地址.jpg","tags":["image","beauty","find_similar"],"relevance_grades":{"商品ID":2,"另一个商品ID":1}}
```

图片先逐个用浏览器打开确认返回 HTTP 200；商品相关性由人工按当前实验商品语料标注。完成 35 条后，评测脚本只读取这一个冻结文件，不再回读或修改 Golden Test。

## 当前商品库的预标注（已写入实验集）

以下数字就是数据库商品 ID；`2` 是强相关，`1` 是弱相关。它们按当前 100 条商品语料的商品标题、类目、价格和约束预标注，后续可在首次人工复核时调整，但同一版实验集冻结后不能再随意改动。

| ID | 相关商品 ID:等级 |
|---|---|
| new-001 | `11:2` |
| new-002 | `1:2, 2:2, 4:2, 9:2, 24:2` |
| new-003 | `13:2, 14:2` |
| new-004 | `64:2, 65:2` |
| new-005 | `61:2, 62:2, 63:2` |
| new-006 | `73:2` |
| new-007 | `45:2, 29:2, 47:2, 48:2` |
| new-008 | `26:2, 27:2, 33:2, 40:2, 42:2` |
| new-009 | `32:2, 43:2` |
| new-010 | `97:2, 98:2, 76:1` |
| new-011 | `82:2, 91:2` |
| new-012 | `84:2, 94:2` |
| new-013 | `6:2` |
| new-014 | `7:2, 12:2` |
| new-015 | `15:2` |
| new-016 | `57:2, 60:1` |
| new-017 | `64:2, 65:2` |
| new-018 | `52:2, 53:2, 70:2` |
| new-019 | `36:2, 44:2, 50:1` |
| new-020 | `41:2` |
| new-021 | `32:2, 43:2` |
| new-022 | `86:2, 87:2, 95:2, 96:2` |
| new-023 | `79:2, 99:2, 90:1` |
| new-024 | `77:2, 76:1` |
| new-025 | `1:2, 2:2, 4:2, 24:2` |
| new-026 | `70:2, 71:2, 53:1` |
| new-027 | `57:2, 58:2, 59:2` |
| new-028 | `32:2, 43:2` |
| new-029 | `84:2, 94:2` |
| new-030 | `11:2` |
| new-031 | `69:2, 74:2` |
| new-032 | `57:2, 58:2, 59:2` |
| new-033 | `32:2, 43:2` |
| new-034 | `6:2, 10:2, 23:2` |
| new-035 | `61:2, 62:2, 63:2` |
