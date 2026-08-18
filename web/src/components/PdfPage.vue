<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import * as pdfjsLib from 'pdfjs-dist'

// 单页渲染：canvas + 文本层。文本层 span 由 JS 动态创建（样式在全局 index.css）
const props = defineProps({
  pageObj: { type: Object, required: true },
  pageNo: { type: Number, required: true },
  scale: { type: Number, required: true },
  visible: { type: Boolean, default: false }
})

const canvasRef = ref(null)
const textLayerRef = ref(null)

let renderTask = null
let seq = 0
let unmounted = false

async function render() {
  const page = props.pageObj
  const canvas = canvasRef.value
  if (!page || !canvas || unmounted) return
  const mySeq = ++seq
  if (renderTask) {
    renderTask.cancel()
    renderTask = null
  }
  const viewport = page.getViewport({ scale: props.scale })
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  canvas.width = Math.floor(viewport.width * dpr)
  canvas.height = Math.floor(viewport.height * dpr)
  canvas.style.width = viewport.width + 'px'
  canvas.style.height = viewport.height + 'px'
  const ctx = canvas.getContext('2d')
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  renderTask = page.render({ canvasContext: ctx, viewport })
  try {
    await renderTask.promise
  } catch (e) {
    if (e && e.name !== 'RenderingCancelledException') console.error(e)
    return
  } finally {
    renderTask = null
  }
  if (unmounted || mySeq !== seq) return
  const textContent = await page.getTextContent()
  if (unmounted || mySeq !== seq) return
  buildTextLayer(textContent, viewport)
}

// 按契约：tx = transform(viewport.transform, item.transform)
// fontHeight = hypot(tx[2], tx[3]); left = tx[4]; top = tx[5] - fontHeight
function buildTextLayer(textContent, viewport) {
  const layer = textLayerRef.value
  if (!layer) return
  layer.innerHTML = ''
  layer.style.width = viewport.width + 'px'
  layer.style.height = viewport.height + 'px'
  const frag = document.createDocumentFragment()
  for (const item of textContent.items) {
    if (!item.str || !item.transform) continue
    const tx = pdfjsLib.Util.transform(viewport.transform, item.transform)
    const fontHeight = Math.hypot(tx[2], tx[3])
    if (!fontHeight || fontHeight <= 0) continue
    const span = document.createElement('span')
    span.className = 'pdf-text-span'
    span.setAttribute('data-page-no', String(props.pageNo))
    span.style.left = tx[4] + 'px'
    span.style.top = tx[5] - fontHeight + 'px'
    span.style.fontSize = fontHeight + 'px'
    span.style.lineHeight = fontHeight + 'px'
    span.textContent = item.str
    frag.appendChild(span)
  }
  layer.appendChild(frag)
}

onMounted(() => {
  if (props.visible) render()
})
watch(
  () => props.visible,
  (v) => {
    if (v) render()
  }
)
watch(
  () => props.scale,
  () => {
    if (props.visible) render()
  }
)

onBeforeUnmount(() => {
  unmounted = true
  seq++
  if (renderTask) {
    try {
      renderTask.cancel()
    } catch {
      /* noop */
    }
  }
})
</script>

<template>
  <div class="pdf-page">
    <canvas ref="canvasRef" class="pdf-canvas"></canvas>
    <div ref="textLayerRef" class="pdf-text-layer"></div>
  </div>
</template>

<style scoped>
.pdf-page {
  position: relative;
}
.pdf-canvas {
  display: block;
  user-select: none;
  -webkit-user-select: none;
}
.pdf-text-layer {
  position: absolute;
  top: 0;
  left: 0;
  overflow: hidden;
  pointer-events: none;
  line-height: 1;
}
</style>
