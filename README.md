# 人类式发言预算 · `astrbot_plugin_reply_budget`

> AstrBot 插件 · 版本 `0.6.1` · 作者 AcceleratorYue · MIT License  
> 仓库：<https://github.com/AcceleratorYue/astrbot_plugin_reply_budget>  
> 兼容：AstrBot `>=4.16,<5`，平台 `aiocqhttp`

一个只做**生成前提示**的 AstrBot 插件：按场景让回复更接近真人聊天，不修改模型已生成的回复。

## 安装

### 插件市场

在 AstrBot WebUI →「插件」→「插件市场」搜索 **人类式发言预算**。

### GitHub

```bash
cd <AstrBot根目录>/data/plugins
git clone https://github.com/AcceleratorYue/astrbot_plugin_reply_budget
```

然后在 AstrBot WebUI →「插件管理」重载插件，或重启 AstrBot。

## 三种场景

### 群聊闲谈

适用：

```text
没有被 @
没有点名
不是明确任务
```

行为：

```text
默认一句 12 字左右，最多 20 字
先说自己的判断或短反应
不逐条接话
看不懂梗就短反应/表情
没有表达欲时可以沉默
主动接话时只补一句最想说的
```

### 被直接对话

适用：

```text
被 @
被点名
私聊
被引用提问
```

行为：

```text
也可能只是闲聊，沿用闲谈的短句、少附和、短反应规则
默认 20 字左右，最多 30 字
被明确提问时正面回答，不为了省字漏关键信息
遇到骚扰、无意义或意义不明的对话，可以 keep_silent
正常直接提问优先回复
```

### 任务/知识

适用：

```text
明确要求详细解释、步骤、代码、教程、分析等
```

行为：

```text
按需要展开
不为了短而省略关键内容
先给结论，再补充
不使用 **加粗**、*斜体*、- 分点、# 标题或表格
需要分步骤时用普通短句分行写
```

## 示例提示词

### 闲谈

```text
<reply_budget>
这是群聊闲谈。默认只发一句 12 字左右，最多 20 字。
先说自己怎么看或给一个短反应；不复述对方，不逐条接话。
看不懂梗、有歧义或容易说错时，短反应/表情包就好，不要硬解释。
……
</reply_budget>
```

### 被直接对话

```text
<reply_budget>
对方在直接和你说话，也可能只是闲聊。默认一句 20 字左右，最多 30 字；需要时正面回答。
先给自己的判断或短反应；被明确提问时正面回答，但不要复述、不要逐条接话。
看不懂梗、有歧义或容易说错时，短反应/表情包就好，不要硬解释。
如果对方是在骚扰、无意义或意义不明，可以调用 keep_silent；正常直接提问则优先回复。
……
</reply_budget>
```

### 任务

```text
<reply_budget>
对方在要完整内容。按需要展开，不要为了短而省略步骤、代码或关键条件。
先给结论，再按对方要求补充；保持聊天口吻，不要写成客服模板。
不要输出 Markdown 标记：不要使用 **加粗**、*斜体*、- 分点、# 标题或表格；需要分步骤时用普通短句分行写。
正常任务不要调用 keep_silent，必须给出内容；只有明显骚扰、无意义或恶意请求才可以沉默。
</reply_budget>
```

## 工具感知

- 只有 `req.func_tool` 中真的存在 `keep_silent` 时，提示词才会提这个工具。
- 只有存在 `search_memes`、`send_meme`、`qq_react` 时，才会提示使用表情包。
- 被直接对话时，遇到骚扰、无意义或意义不明的请求可以沉默；正常直接提问优先回复。
- 明确任务时，正常任务必须回答；只有明显骚扰、无意义或恶意请求才允许沉默。

## 配置

```text
enable                    总开关
human_speech_mode         启用场景化策略（默认 true）
enable_in_groups          群聊启用
enable_in_private         私聊启用
casual_target_chars       闲谈目标字数（默认 12）
casual_max_chars          闲谈上限（默认 20）
direct_target_chars       直接对话目标字数（默认 20）
direct_max_chars          直接对话上限（默认 30）
silence_mode              off / conditional / aggressive（默认 conditional）
task_keywords             任务模式关键词
soft_budget_chars         旧版统一预算（仅 human_speech_mode=false 时使用）
prefer_own_view           优先说自己的观点
use_meme_fallback         看不懂时用短反应/表情包
avoid_word_repetition     避免一句话重复用词
sarcasm_aware             识别反讽与语境反转
experience_guard          不编造真实生活经历
knowledge_fallback        允许转为知识/判断型回答
debug_log                 输出模式判断日志
```

## 设计边界

```text
只做生成前提示
不做事后改写
不修改模型已经生成的回复
不切换模型或 Provider
不改变人格文件
```

提示词只能提高行为倾向，不能保证模型每次严格执行。

## 许可证

MIT License，详见 [LICENSE](LICENSE)。
