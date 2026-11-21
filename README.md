# DeepStudy

从文章出发的英语学习工具：先学文章里的词汇和语法，再解锁原文练习。学习记录保存在本地浏览器，可在“数据与来源”导出或导入 JSON。

## 学习流程

1. 选择一篇文章，系统抽取原文中的词形；冠词、介词等进入语法学习，其余词进入词汇学习。
2. 每个新词先看原词和上下文、填写确认过的释义，再遮住词形做拼写回忆。拼写正确才记为掌握；看过答案的词会回到稍后复习队列。
3. 每个语法组先看规则，再从文章原句中完成填空；答对后才算完成。
4. 词汇与语法先修都完成后，文章解锁逐句跟写。译文由学习者自行填写。

## 内容来源

应用内置 4 篇 Simple English Wikipedia 开篇节选：Climate change、Renewable energy、Computer、Atlantic Ocean。每篇保留来源链接、许可和修订信息。材料是否可再利用须按作品授权与适用地区分别确认；普通网页可访问不代表可复制或批量抓取。

## 采集器

`tools/collect_mediawiki.py` 使用 MediaWiki API 采集文章候选；输出默认待校订。示例：

```powershell
python tools/collect_mediawiki.py --query "climate change" --query "solar energy" --query "computer" --count 5 --max-words 260 --user-agent "DeepStudy/0.1 (mailto:you@example.com)" --output data/mediawiki-seeds.json --js-output app/seed-data.js
python tools/merge_corpora.py data/mediawiki-seeds.json --output data/deepstudy-import.json --js-output app/seed-data.js
```

采集器不替代逐页许可审查，也不用于无差别抓取博客、剧本或受版权限制的网页。
