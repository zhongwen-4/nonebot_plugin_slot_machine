<div align="center">
  <a href="https://v2.nonebot.dev/">
    <img src="https://nonebot.dev/logo.png" width="180" height="180" alt="nonebot">
  </a>

# nonebot-plugin-slot-machine

_✨ NoneBot2 老虎/老虎机与打螺丝金币插件 ✨_

<a href="https://github.com/zhongwen-4/nonebot_plugin_slot_machine/actions/workflows/publish.yml">
  <img src="https://img.shields.io/github/actions/workflow/status/zhongwen-4/nonebot_plugin_slot_machine/publish.yml?style=flat-square" alt="workflow">
</a>
<a href="https://pypi.org/project/nonebot-plugin-slot-machine/">
  <img src="https://img.shields.io/pypi/v/nonebot-plugin-slot-machine.svg?style=flat-square" alt="pypi">
</a>
<img src="https://img.shields.io/badge/python-3.11+-blue.svg?style=flat-square" alt="python">
<img src="https://img.shields.io/badge/nonebot-2.x-red.svg?style=flat-square" alt="nonebot">

</div>

## 📖 介绍

一个基于 NoneBot2 的老虎机插件，支持注册金币账户、投注设置、老虎机抽奖、转账、查询，以及内置的“打螺丝”金币获取玩法。

老虎机为 5 行 6 列盘面，包含普通符号、百搭符号和夺宝符号。中奖结果会绘制成图片发送，中奖轮数较多时自动使用合并转发。

## 💿 安装

使用 pip 安装：

```bash
pip install nonebot-plugin-slot-machine
```

使用 nb-cli 安装：

```bash
nb plugin install nonebot-plugin-slot-machine
```

## ⚙️ 配置

本插件会通过 `nonebot-plugin-localstore` 自动管理数据文件，无需额外配置数据库路径。

需要安装并配置 Milky 适配器：

```bash
pip install nonebot-adapter-milky
```

## 🎉 使用

在 NoneBot 项目中加载插件：

```python
nonebot.load_plugin("slot_machine.plugins.slot_machine")
```

如果使用 `pyproject.toml` 的本地插件目录加载，请确保插件目录包含：

```toml
[tool.nonebot]
plugin_dirs = ["slot_machine/plugins"]
```

### 指令

| 指令 | 说明 |
| --- | --- |
| `注册老虎机` / `注册` | 注册账号，每人赠送初始金币 |
| `设置投注 <投注大小> <投注倍数>` | 设置投注，投注大小支持 `0.02`、`0.2`、`1`，倍数为 `1-10` |
| `开始旋转` | 按当前投注设置开始抽奖 |
| `查询老虎机` / `查询` | 查看金币、抽奖次数、中奖次数和投注设置 |
| `转账 <账号> <金额>` | 向其他已注册账号转账金币 |
| `开始打螺丝 <分钟>` | 按普通模式立即打工结算 |
| `开始打螺丝 <模式> <分钟>` | 使用指定模式打工，模式：普通、韭菜、牛马、卷王 |
| `打螺丝状态` / `螺丝状态` | 查看体力和打工状态 |
| `停止打螺丝` | 结算并停止历史工作状态 |

### 示例

```text
注册老虎机
设置投注 0.2 5
开始旋转
查询老虎机
转账 123456 10
开始打螺丝 牛马 10
```

## 🎰 玩法说明

- 中奖需要从第一列开始连续命中，同符号可由百搭符号补位。
- 每次中奖后会消除中奖符号并补充新符号，奖金倍数翻倍，最高 1024 倍。
- 盘面任意位置出现 3 个夺宝符号可获得免费抽奖机会，超过 3 个时每多 1 个增加 10 次。
- 打螺丝体力上限为 100，每 30 秒恢复 1 点。

## 📦 数据存储

插件数据使用 SQLite，并通过 `nonebot-plugin-localstore` 存放在插件数据目录中。缓存图片会写入插件缓存目录，发送完成后自动删除。

## 🙏 致谢

- [NoneBot2](https://v2.nonebot.dev/)
- [nonebot-plugin-template](https://github.com/A-kirami/nonebot-plugin-template)
- [nonebot-adapter-milky](https://github.com/nonebot/adapter-milky)
