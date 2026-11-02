<script setup>
import { computed } from "vue";
import { useSlideContext } from "@slidev/client";
import { slides } from "#slidev/slides";

const { $page } = useSlideContext();
const mainSlideCount = computed(() => {
  const appendixStart = slides.value.findIndex(slide => slide.meta.slide.frontmatter.appendix);
  return appendixStart === -1 ? slides.value.length : appendixStart;
});
</script>

<template>
  <div class="slidev-layout talk">
    <div class="slide-content"><slot /></div>
    <footer class="deck-footer">
      <span></span>
      <span v-if="$page <= mainSlideCount">{{ String($page).padStart(2, "0") }} <b>/</b> {{ String(mainSlideCount).padStart(2, "0") }}</span>
    </footer>
  </div>
</template>
