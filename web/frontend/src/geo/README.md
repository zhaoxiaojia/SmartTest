# Global 背景地理素材

`global-boundaries.json` 是本地展示素材，不代表部署范围或业务查询结果。

- 陆地：Natural Earth 1:110m，world-atlas 2.0.2 `countries-110m.json` 的 land。
- 常驻国境线：同一1:110m数据的 countries，以临时 topojson-client `mesh(topology, countries, (a,b) => a !== b)` 提取共享国境；沿海轮廓由 land 保持。159条线、2807坐标，不引入全部50m国家面重绘。
- 国家/地区：Natural Earth 1:50m，world-atlas 2.0.2 `countries-50m.json`；保留办公城市/客户总部对应区域。香港单独地区轮廓，其他非美区域采用国家轮廓。
- 美国 California (06)、Washington (53)、Arkansas (05)：US Census 2017 cartographic boundaries，由 us-atlas 3.0.1 `states-10m.json` 提供未投影经纬度。
- 提取：临时 topojson-client 3.1.0 `feature()`，只保留 geometry/id，坐标四舍五入至0.001度。不手写/替换边界。转换工具不进入项目依赖。

下载与许可：
- https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-110m.json
- https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-50m.json
- https://cdn.jsdelivr.net/npm/us-atlas@3.0.1/states-10m.json
- https://github.com/topojson/world-atlas （分发代码 ISC，Natural Earth 数据 public domain）
- https://www.naturalearthdata.com/about/terms-of-use/
- https://github.com/topojson/us-atlas （分发代码 ISC，US Census 数据 public domain）

Office 名单：https://www.amlogic.com/about/ 。Customer 表示公开关联客户的总部代表城市，不表示产品部署位置：Google Mountain View、Amazon Seattle、Walmart Bentonville、Deutsche Telekom Bonn、Sky Isleworth。
关联来源：[2026半年报](https://static.cninfo.com.cn/finalpage/2026-08-20/1225482822.PDF)、[2025半年报](https://static.cninfo.com.cn/finalpage/2025-08-13/1224461921.PDF)，及 [Amlogic 官网新闻](https://www.amlogic.com/news/) 2026-09-14 IBC2026 Deutsche Telekom 发布（[原文转载](https://natlawreview.com/press-releases/ibc-2026-amlogic-x-deutsche-telekom-elevate-global-stb-experiences-edge-ai)）。坐标是城市中心的展示近似值，不是办公室建筑地址。区域等级：美国三州为 state，香港为 region，其他为 country；界线仅作相关区域示意。

绘制：d3-geo 3.1.1（ISC），https://github.com/d3/d3-geo/blob/main/LICENSE 。正射投影、真实自转和半球裁剪由库处理；页面不请求外部地图。

总部来源：[Google](https://about.google/company-info/locations/)、[Amazon](https://www.amazon.jobs/content/en/locations)、[Walmart](https://corporate.walmart.com/about/newhomeoffice/explore-the-new-campus/tour)、[Deutsche Telekom](https://www.telekom.com/de/allgemein/impressum)、[Sky](https://skygroup.sky/en-gb/about/our-governance)。

低分辨率海岸线为制图概化数据，例如 Istanbul 中心可落在50m海岸线外数公里；展示点保持真实城市近似坐标，不因概化轮廓修改位置。

七大洲/五大洋采用英文地理名称与大陆/海域内部近似展示锚点；锚点随正射投影旋转，仅正面且落入裁切视口时常驻显示，不参与地点轮显或闪烁。Pacific Ocean使用跨日期线两个锚点，当前可见范围同名最多显示一次。紧凑surface继续不显示名称。
