<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import PdfReader from '@/components/PdfReader.vue'

const route = useRoute()
const documentId = computed(() => route.params.id)
</script>

<template>
  <PdfReader :document-id="documentId" />
</template>
