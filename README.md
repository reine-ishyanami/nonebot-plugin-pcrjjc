# nonebot-plugin-pcrjjc

### 介绍

* 基于[pcrjjc_huannai](https://github.com/SonderXiaoming/pcrjjc_huannai)的代码基础上进行重构
* 可独立作为nonebot2插件使用，不依赖于HoshinoBot

### 具体指令如下

![竞技场帮助指令](./img/help.png)

### 配置

**在nonebot2项目中的`.env`开头的文件添加下表配置项，其中非必填项可不填**

|     配置项     |   类型    | 是否必填 | 默认值  |              说明              |
| :------------: | :-------: | :------: | :-----: | :----------------------------: |
|   SUPERUSERS   | list[str] |   True   |         | 超级用户QQ号，示例：["114514"] |
|    VERSION     |    str    |  False   | "6.2.0" |          客户端版本号          |
|    MAX_PRI     |    int    |  False   |    0    |          最大私聊人数          |
|   MAX_PCRID    |    int    |  False   |    8    |       每人绑定的最大数量       |
|  MAX_HISTORY   |    int    |  False   |   50    |        单人最多历史记录        |
| NOTICE_CD_MIN  |    int    |  False   |   10    |  上线提醒时间间隔（单位：分）  |
| REFRESH_SECOND |    int    |  False   |    3    |    排名刷新频率（单位：秒）    |

