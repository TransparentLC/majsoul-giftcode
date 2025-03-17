# majsoul-giftcode

雀魂礼品码及奖励内容爬取脚本。

成品：[JSON 格式数据](https://i.akarin.dev/majsoul-giftcode.json)、[RSS 订阅](https://i.akarin.dev/majsoul-giftcode.xml)

除 `requirements.txt` 以外还需要安装 [ffmpeg](https://ffmpeg.org/download.html)，爬取后的礼品码内容会保存为 `giftcode.{json,xml}`。

## 原理

![](https://p.sda1.dev/22/2f675f4da690485cc77071b61d0d3ec8)

B 站的一些 up 主会在猫粮发布礼品码情报时第一时间发布使用礼品码领取奖励的录像，并将礼品码写在视频标题上（如图所示），因此可以根据这个进行爬取。

详细流程：

1. 在 B 站按照“最新发布”的顺序搜索“雀魂礼品码”或“雀魂礼包码”
2. 筛选标题符合以下条件的视频：
   * 包含“雀魂”（否则会匹配到其他游戏的礼品码情报视频）
   * 包含连续的 8 个以上字母和数字（如果是“或”的话会匹配到标题中含有形如 20250101 的日期的无关视频）
3. 下载视频
   * 目前使用 https://api.injahow.cn/bparse/ 的 API 进行解析
4. 对视频按照一秒 3 帧进行截图
   * 为了优化识别速度，将截图裁剪为边长为视频高度 2/3 的正中间的矩形部分
5. 识别出现了“获得奖励”标题的第一帧和最后一帧
6. 取这两帧中间的一帧，识别各个道具的图标是否有在这一帧中出现
   * 由于道具图标在视频中出现的大小是不确定的，因此图像识别没有使用 [Template Matching](https://docs.opencv.org/4.x/d4/dc6/tutorial_py_template_matching.html)，而是使用基于 SIFT 和 FLANN 的 [Feature Matching](https://docs.opencv.org/4.x/dc/dc3/tutorial_py_matcher.html)
   * 如果视频不是领取奖励的录像（例如对着仓库界面一图流），则无法正确识别奖励内容
   * 可以人工在 `giftcode.json` 中编辑礼品码对应的奖励内容
