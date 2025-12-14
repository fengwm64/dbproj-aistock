<template>
    <div class="app-analytics">
        <slot />
    </div>
</template>

<script setup>
import { onMounted } from 'vue'

onMounted(() => {
    try {
        const script = document.createElement('script')
        script.defer = true
        script.src = 'https://ana.102465.xyz/hello'
        script.setAttribute('data-website-id', '61825d9e-9921-44de-adc7-8152ca5c24d5')
        document.head.appendChild(script)
        console.log('Analytics script loaded')
    } catch (error) {
        console.error('Failed to load Analytics script:', error)
    }
})
</script>