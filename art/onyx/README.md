# 玄翼 · City Drive 車庫

採用概念 B 的鈦灰賽道超跑。頭燈為外側三段式直立燈，尾部以架高橋式尾翼、垂直尾燈及雙通道擴散器辨識。車身由共享比例的縱向控制截面與閉合車身面構成，四輪、碟盤、卡鉗、玻璃、導流板與燈具可在 Blender 分別編輯。外觀用概念稿選定，造型細節以 Blender 幾何為準。

模型單位是公尺，Blender 坐標以 +Y 為車頭、+Z 向上，glTF 轉換後以 -Z 為車頭、+Y 向上。軸距 2.78 m，外廓約 4.86 × 2.14 × 1.33 m，外廓包括尾翼、輪胎及空力件。設計包的四視圖用同一車模做正投影，包含正面、背面、側面與頂視。

## 重建

```bash
blender -b --factory-startup --python-exit-code 1 --python art/onyx/build.py -- out --render
npx --yes gltfpack@1.3.0 -i out/onyx.glb -o assets/onyx.glb -c -vp 16 -vt 14 -vn 12 -km
```

移除 `--render` 可只建立原始檔、貼圖與未壓縮 GLB。Blender 以 Principled BSDF 製作 13 種 PBR 材質，碳纖維 PNG 同時保存在檔案旁並封裝進 .blend。車庫的 Meshopt GLB 保留材質名稱，模型由 Three.js 載入。車庫棚燈預先烘成反射圖，車身使用環境反射、接觸柔影與預繪方向光陰影。

本地可用 `python -m http.server 8000` 從專案根目錄預覽。網站入口是車庫。駕駛版完整保留於 GitHub 分支 `backup/free-drive-709fefd`，指向 `709fefd013cf91eb0f8786a6d7bcfbaa426ba534`。
