<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  ArrowLeft,
  Mail,
  Globe,
  Heart,
  Code,
  Palette,
  Sparkles,
  MapPin,
  Clock,
  Github,
  Twitter,
  ExternalLink,
  Award,
  BookOpen,
  Zap,
  Cpu
} from 'lucide-vue-next'
import logoImage from '../../assets/images/Luminous_chenxi.png'
import LumiSettingsBackground from '../../components/settings-detail/LumiSettingsBackground.vue'
import '../../styles/views/settings-independent-bg.css'

const router = useRouter()
const { t } = useI18n()

const profileStats = [
  { icon: Github, label: 'Followers', value: '65+' },
  { icon: Heart, label: 'Following', value: '140' },
  { icon: MapPin, label: 'Location', value: 'China' },
  { icon: Clock, label: 'Timezone', value: 'UTC+8' }
]

const socialLinks = [
  { icon: Github, label: 'GitHub', url: 'https://github.com/luminous-ChenXi' },
  { icon: Twitter, label: 'X / Twitter', url: 'https://x.com/luminous_chenxi' },
  { icon: Mail, label: 'Email', url: 'mailto:luminouschenxi@outlook.com' },
  { icon: Globe, label: 'Blog', url: 'https://luminouschenxi.com' },
  { icon: Globe, label: 'Project', url: 'https://luminouschenxi.net' }
]

const pinnedProjects = [
  {
    name: 'LuomiNest',
    key: 'luomiNest',
    owner: 'LuminousCX',
    url: 'https://github.com/LuminousCX/LuomiNest',
    tags: ['Vue 3', 'Electron', 'FastAPI']
  },
  {
    name: 'LuomiBlog',
    key: 'luomiBlog',
    owner: 'luminous-ChenXi',
    url: 'https://github.com/luminous-ChenXi/LuomiBlog',
    tags: ['Astro', 'Vue', 'Spring Boot']
  },
  {
    name: 'AsrNest',
    key: 'asrNest',
    owner: 'luminous-ChenXi',
    url: 'https://github.com/luminous-ChenXi/AsrNest',
    tags: ['Spring Boot', 'Vue 3', 'AI']
  },
  {
    name: 'AsrNest Backend',
    key: 'asrNestBackend',
    owner: 'luminous-ChenXi',
    url: 'https://github.com/luminous-ChenXi/AsrNest-Backend',
    tags: ['Java', 'MySQL', 'Redis']
  }
]

const techStacks = computed(() => [
  { category: t('about.techStacks.backend'), icon: Code, items: ['Java', 'Python', 'Node.js', 'Nginx', 'Docker', 'K8s', 'MySQL', 'MongoDB'] },
  { category: t('about.techStacks.frontend'), icon: Globe, items: ['Vue', 'Astro', 'HTML/CSS', 'TypeScript', 'WordPress'] },
  { category: t('about.techStacks.creative'), icon: Palette, items: ['UE5', 'Blender', 'AE', 'PS'] }
])
</script>

<template>
  <div class="lumi-settings-page about-view">
    <LumiSettingsBackground />
    <header class="lumi-settings-page__header lumi-settings-animate-fade">
      <button class="lumi-settings-page__back" @click="router.push('/settings')">
        <ArrowLeft :size="18" />
      </button>
      <div>
        <h1 class="lumi-settings-page__title">{{ t('about.title') }}</h1>
        <p class="lumi-settings-page__subtitle">{{ t('about.subtitle') }}</p>
      </div>
    </header>

    <div class="lumi-settings-page__body">
      <div class="lumi-settings-page__content">
        <!-- Profile Hero -->
        <section class="about-hero lumi-settings-animate-slide">
          <div class="about-profile">
            <div class="about-logo">
              <img :src="logoImage" alt="LuminousChenXi" />
            </div>
            <div class="about-identity">
              <h2 class="about-name">Chenxi / 辰汐</h2>
              <p class="about-role">Full-Stack Developer & Digital Creative Explorer</p>
              <p class="about-motto">
                “Nothing but youth and dreams can live up to the future!”<br />
                {{ t('about.mottoZh') }}
              </p>

              <div class="about-stats">
                <div v-for="stat in profileStats" :key="stat.label" class="about-stat">
                  <component :is="stat.icon" :size="14" />
                  <span>{{ stat.value }} {{ stat.label }}</span>
                </div>
              </div>

              <div class="about-social">
                <a
                  v-for="link in socialLinks"
                  :key="link.label"
                  :href="link.url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="about-social__link"
                >
                  <component :is="link.icon" :size="14" />
                  <span>{{ link.label }}</span>
                </a>
              </div>
            </div>
          </div>
        </section>

        <!-- About Me -->
        <section class="lumi-settings-section lumi-settings-animate-slide">
          <div class="lumi-settings-section__header">
            <Sparkles :size="14" />
            <span>{{ t('about.sections.aboutMe') }}</span>
          </div>
          <div class="about-section">
            <p class="about-section__text">
              {{ t('about.aboutMe.p1a') }}<strong>{{ t('about.aboutMe.p1Strong') }}</strong>{{ t('about.aboutMe.p1b') }}
            </p>
            <p class="about-section__text">
              I am a Full-Stack Developer & Digital Creative Explorer, passionately bridging the gap between
              cutting-edge technology (AI, Cloud-Native) and imaginative creation (Anime, Game Dev).
              My mission is to build practical, innovative projects that are both technically robust and creatively engaging.
            </p>
          </div>
        </section>

        <!-- Technical Focus -->
        <section class="lumi-settings-section lumi-settings-animate-slide">
          <div class="lumi-settings-section__header">
            <Cpu :size="14" />
            <span>{{ t('about.sections.technicalFocus') }}</span>
          </div>
          <div class="about-section">
            <p class="about-section__text">{{ t('about.technicalFocusText') }}</p>
          </div>
        </section>

        <!-- Creative Practice -->
        <section class="lumi-settings-section lumi-settings-animate-slide">
          <div class="lumi-settings-section__header">
            <Palette :size="14" />
            <span>{{ t('about.sections.creativePractice') }}</span>
          </div>
          <div class="about-section">
            <p class="about-section__text">{{ t('about.creativePracticeText') }}</p>
          </div>
        </section>

        <!-- Pinned Projects -->
        <section class="lumi-settings-section lumi-settings-animate-slide">
          <div class="lumi-settings-section__header">
            <Zap :size="14" />
            <span>{{ t('about.sections.coreProjects') }}</span>
          </div>
          <div class="about-projects">
            <a
              v-for="project in pinnedProjects"
              :key="project.name"
              :href="project.url"
              target="_blank"
              rel="noopener noreferrer"
              class="about-project-card"
            >
              <div class="about-project__header">
                <span class="about-project__name">{{ project.name }}</span>
                <ExternalLink :size="12" />
              </div>
              <span class="about-project__owner">{{ project.owner }}</span>
              <p class="about-project__desc">{{ t('about.projects.' + project.key) }}</p>
              <div class="about-project__tags">
                <span v-for="tag in project.tags" :key="tag" class="lumi-settings-tag">{{ tag }}</span>
              </div>
            </a>
          </div>
        </section>

        <!-- Tech Stack -->
        <section class="lumi-settings-section lumi-settings-animate-slide">
          <div class="lumi-settings-section__header">
            <Code :size="14" />
            <span>{{ t('about.sections.techStack') }}</span>
          </div>
          <div class="about-tech">
            <div v-for="stack in techStacks" :key="stack.category" class="about-tech__row">
              <div class="about-tech__label">
                <component :is="stack.icon" :size="13" />
                <span>{{ stack.category }}</span>
              </div>
              <div class="about-tech__tags">
                <span v-for="item in stack.items" :key="item" class="lumi-settings-tag">{{ item }}</span>
              </div>
            </div>
          </div>
        </section>

        <!-- Contact -->
        <section class="lumi-settings-section lumi-settings-animate-slide">
          <div class="lumi-settings-section__header">
            <Mail :size="14" />
            <span>{{ t('about.sections.contact') }}</span>
          </div>
          <div class="about-contact">
            <a href="mailto:luminouschenxi@outlook.com" class="about-contact__item">
              <Mail :size="14" />
              <span>luminouschenxi@outlook.com</span>
            </a>
            <a href="mailto:chenxi@luminouschenxi.net" class="about-contact__item">
              <Mail :size="14" />
              <span>chenxi@luminouschenxi.net</span>
            </a>
            <a href="https://luminouschenxi.com" target="_blank" rel="noopener noreferrer" class="about-contact__item">
              <BookOpen :size="14" />
              <span>luminouschenxi.com</span>
            </a>
            <a href="https://luminouschenxi.net" target="_blank" rel="noopener noreferrer" class="about-contact__item">
              <Globe :size="14" />
              <span>luminouschenxi.net</span>
            </a>
          </div>
        </section>

        <!-- Support -->
        <section class="lumi-settings-card lumi-settings-animate-slide">
          <div class="about-support">
            <Heart :size="14" class="about-support__icon" />
            <span>{{ t('about.support.before') }}</span>
            <a href="https://afdian.com/a/luminous_chenxi" target="_blank" rel="noopener noreferrer">{{ t('about.support.afdian') }}</a>
            <span>{{ t('about.support.after') }}</span>
          </div>
        </section>

        <!-- Achievements hint -->
        <section class="lumi-settings-card lumi-settings-animate-slide">
          <div class="about-section">
            <p class="about-section__text">
              <Award :size="14" class="about-award-icon" />
              GitHub Achievements · Open Source Contributor · LuomiNest / LuomiBlog / AsrNest Maintainer
            </p>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped src="../../styles/views/about-view.css"></style>

<style scoped>
/* 背景由 settings-independent-bg.css 独立控制 */
</style>
