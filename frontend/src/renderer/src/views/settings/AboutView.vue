<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ArrowLeft, Mail, Globe, Heart, Code, Palette, Sparkles } from 'lucide-vue-next'
import logoImage from '../../assets/images/Luminous_chenxi.png'

const router = useRouter()

const techStacks = [
  { category: '后端/运维', icon: Code, items: ['Java', 'Python', 'Node.js', 'Nginx', 'Docker', 'K8s', 'MySQL', 'MongoDB'] },
  { category: '前端/建站', icon: Globe, items: ['Vue', 'HTML/CSS', 'TypeScript', 'WordPress'] },
  { category: '创作/设计', icon: Palette, items: ['UE5', 'Blender', 'AE', 'PS'] }
]
</script>

<template>
  <div class="about-view">
    <header class="about-header page-header animate-fade-in">
      <div class="page-header__main">
        <button class="page-header__back" @click="router.push('/settings')">
          <ArrowLeft :size="18" />
        </button>
        <div>
          <h1 class="page-header__title">关于开发者</h1>
          <p class="page-subtitle">LuomiNest 项目主导者</p>
        </div>
      </div>
    </header>

    <div class="about-body">
      <div class="profile-card animate-slide-up">
        <div class="profile-banner">
          <img :src="logoImage" alt="LuminousChenXi" class="profile-logo" />
          <div class="profile-identity">
            <h2 class="profile-name">Chenxi / 辰汐</h2>
            <p class="profile-role">Full-Stack Developer & Digital Creative Explorer</p>
            <p class="profile-alias">Luminous-ChenXi Qiushui / 辰汐秋水</p>
          </div>
        </div>

        <div class="profile-section">
          <h3 class="profile-h3"><Sparkles :size="14" /> About Me / 关于我</h3>
          <p>
            我是一名<strong>全栈开发者与数字创意探索者</strong>，热衷于将前沿技术（AI、云原生）与创意构想（二次元、游戏开发）相结合。
            我的目标是构建既技术扎实又富有创意的实用项目。LuomiNest 由我主导设计与开发。
          </p>
        </div>

        <div class="profile-section">
          <h3 class="profile-h3"><Code :size="14" /> Tech Stack / 技术栈</h3>
          <div class="tech-grid">
            <div v-for="stack in techStacks" :key="stack.category" class="tech-row">
              <div class="tech-label">
                <component :is="stack.icon" :size="13" />
                <span>{{ stack.category }}</span>
              </div>
              <div class="tech-tags">
                <span v-for="item in stack.items" :key="item" class="tech-tag">{{ item }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="profile-section">
          <h3 class="profile-h3"><Globe :size="14" /> Core Project / 核心项目</h3>
          <p>
            主导开发 <a href="https://luminouschenxi.net" target="_blank" rel="noopener noreferrer">LuminousChenXi</a> ——
            基于 Spring Boot & Vue 3 的现代图床平台。核心功能：AI 预审、CDN 加速、便捷上传。
          </p>
          <p>
            技术博客 <a href="https://luminouschenxi.com" target="_blank" rel="noopener noreferrer">luminouschenxi.com</a> ——
            分享网络配置、开源协议等技术心得。
          </p>
        </div>

        <div class="profile-section">
          <h3 class="profile-h3"><Mail :size="14" /> Contact / 联系方式</h3>
          <div class="contact-links">
            <a href="mailto:chenxi@luminouschenxi.net" class="contact-item">
              <Mail :size="13" />
              <span>chenxi@luminouschenxi.net</span>
            </a>
            <a href="https://luminouschenxi.com" target="_blank" rel="noopener noreferrer" class="contact-item">
              <Globe :size="13" />
              <span>luminouschenxi.com</span>
            </a>
            <a href="https://luminouschenxi.net" target="_blank" rel="noopener noreferrer" class="contact-item">
              <Globe :size="13" />
              <span>luminouschenxi.net</span>
            </a>
          </div>
        </div>

        <div class="profile-support">
          <Heart :size="13" class="support-icon" />
          <span>如果你觉得我的项目对你有帮助，欢迎通过</span>
          <a href="https://afdian.com/a/luminous_chenxi" target="_blank" rel="noopener noreferrer">爱发电</a>
          <span>支持我</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.about-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--workspace-bg);
  overflow: hidden;
}

.about-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-5) var(--space-7);
  border-bottom: 1px solid var(--workspace-border);
  flex-shrink: 0;
  margin-bottom: 0;
}

.page-subtitle {
  font-size: var(--text-sm);
  color: var(--text-muted);
  margin-top: 1px;
}

.about-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-6) var(--space-7);
}

.profile-card {
  background: var(--workspace-card);
  border-radius: var(--radius-lg);
  padding: var(--space-7);
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.profile-banner {
  display: flex;
  align-items: center;
  gap: var(--space-5);
}

.profile-logo {
  width: 170px;
  height: 170px;
  border-radius: var(--radius-lg);
  object-fit: cover;
  flex-shrink: 0;
}

.profile-identity {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.profile-name {
  font-size: var(--text-3xl);
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.3px;
}

.profile-role {
  font-size: var(--text-base);
  color: var(--lumi-primary);
  font-weight: 500;
}

.profile-alias {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.profile-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.profile-h3 {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-md);
  font-weight: 600;
  color: var(--text-primary);
  opacity: 0.85;
}

.profile-section p {
  font-size: var(--text-base);
  color: var(--text-secondary);
  line-height: 1.75;
}

.profile-section strong {
  color: var(--text-primary);
  font-weight: 600;
}

.profile-section a {
  color: var(--lumi-primary);
  text-decoration: none;
  font-weight: 500;
  transition: color var(--transition-fast);
}

.profile-section a:hover {
  color: var(--lumi-primary-hover);
  text-decoration: underline;
}

.tech-grid {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.tech-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.tech-label {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-muted);
  min-width: 90px;
  flex-shrink: 0;
}

.tech-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.tech-tag {
  font-size: var(--text-xs);
  font-weight: 500;
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-sm);
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.contact-links {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.contact-item {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-base);
  color: var(--text-secondary);
  text-decoration: none;
  transition: color var(--transition-fast);
}

.contact-item:hover {
  color: var(--lumi-primary);
}

.profile-support {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  color: var(--text-muted);
  padding-top: var(--space-2);
  border-top: 1px solid var(--divider-soft);
}

.support-icon {
  color: var(--lumi-accent);
  flex-shrink: 0;
}

.profile-support a {
  color: var(--lumi-primary);
  text-decoration: none;
  font-weight: 500;
  transition: color var(--transition-fast);
}

.profile-support a:hover {
  color: var(--lumi-primary-hover);
  text-decoration: underline;
}

</style>
