// @ts-check
import { defineConfig } from '@vivliostyle/cli';

export default defineConfig({
  title: "{{TITLE}}",
  author: "{{AUTHOR}}",
  language: "ja",
  // 縦書き（右綴じ）は "rtl"、横書き（左綴じ）は "ltr"
  readingProgression: "{{PROGRESSION}}",
  size: "{{SIZE}}",
  // テーマは版を固定する（版が上がると改行位置やページ数が変わる為）
  theme: [
    "{{THEME}}",
    "./custom.css",
  ],
  entryContext: "draft",
  // 章を足したらここに加える。output は英字で始まる名前にする
  // （数字で始まるとEPUBの中の識別子が不正になり、epubcheckでエラーになる）
  entry: [
    { path: "01_chapter1.md", output: "chapter1.html" },
  ],
  toc: {
    title: "目次",
    htmlPath: "toc.html",
  },
  output: [
    { path: "{{SLUG}}.pdf", format: "pdf" },
    { path: "{{SLUG}}.epub", format: "epub" },
  ],
});
