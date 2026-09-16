<script setup lang="ts">
/**
 * 用户协议详情页（/settings/terms-detail）
 *
 * 风格完全仿 PrivacyDetailView：独立背景 + lumi-settings-page 版式 + 分节滚动渐显。
 * 分节标题走 i18n（terms.sections.*），正文为固定产品自述文本；
 * 首启向导 StepAgreement 经 from=welcome 查询参数打开本页，返回时回退向导而非设置页。
 *
 * 注：本页为产品自述文本，正式发布前建议经法务审阅。
 */
import { useRouter, useRoute } from 'vue-router'
import { ArrowLeft, FileText, Scale, Bot, UserCheck, Gavel, Copyright, ShieldAlert, RefreshCw, Trash2, Users } from 'lucide-vue-next'
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import LumiSettingsBackground from '../../components/settings-detail/LumiSettingsBackground.vue'
import '../../styles/views/settings-independent-bg.css'

const router = useRouter()
const route = useRoute()
const { t } = useI18n()

/** 协议版本（与向导 StepAgreement 记录进 config.onboarding 的版本一致） */
const TERMS_VERSION = '1.0.0'

const sections = [
  {
    key: 'serviceNature',
    content: [
      'LuomiNest 是一款本地优先的 AI 桌面助手，由 LuminousChenXi 团队开发并按开源许可证发布。应用的核心对话、记忆与自动化能力默认在您的本地设备上运行，数据（对话记录、配置、偏好等）默认存储于本机。',
      '本应用的部分可选能力（如在线 AI 模型推理、语音合成、云端模型额度、显示偏好多端同步）需要连接外部服务。您可以在设置中自行开启或关闭这些能力，关闭后应用仍可离线运行。',
      '您与 AI 系统交互时，应用会明确告知您正在与 AI 系统而非真人交互。AI 生成的内容可能存在错误、遗漏或不当表述，请自行判断后再采用。',
      '本协议是您与开发团队之间关于使用本应用的约定。您下载、安装或使用本应用，即表示您已阅读并同意本协议的全部内容。'
    ]
  },
  {
    key: 'accounts',
    content: [
      '本地账号：您可以在本机创建本地账号（用户名 + 密码），用于身份识别、偏好管理与访问控制。本地账号信息仅保存在本机，密码经加密存储，开发团队无法读取或找回。',
      '辰汐通行证（云账号）：您可以选择使用辰汐通行证登录（Device Flow 设备授权登录，无需在本应用内输入通行证密码），以使用云端模型额度、云端模型目录与显示偏好多端同步等能力。通行证的注册与使用还受通行证服务自身协议约束。',
      '账号切换与登出：您可以随时在设置中退出登录或切换通行证账号。退出登录将清除本机保存的云端令牌；AI 调用将回落到本地模型配置。',
      '您应对账号及凭证的保管负责。因您主动分享凭证、密码或授权页用户码导致的账号安全问题，由您自行承担相应责任。'
    ]
  },
  {
    key: 'conduct',
    content: [
      '您承诺在使用本应用及接入的任何服务时，遵守所在国家或地区的法律法规，包括但不限于《中华人民共和国网络安全法》《生成式人工智能服务管理暂行办法》等（中国大陆用户），以及您所在司法辖区的相应法律。',
      '您不得利用本应用从事以下行为：生成、传播违法违规内容；侵犯他人知识产权、名誉权、隐私权等合法权益；危害网络安全或未经授权访问他人系统；批量注册、滥用或攻击本应用依赖的服务接口。',
      '您不得对应用进行逆向工程以规避授权限制，或将以云端额度获得的服务能力转售、再分配给第三方。',
      '若您违反上述规范，开发团队有权暂停或终止向您提供云端服务能力，并保留依法追究责任的权利。'
    ]
  },
  {
    key: 'ip',
    content: [
      '本应用的源代码按项目 LICENSE（AGPL-3.0 及随附的特殊许可说明）授权使用；LuciNest 名称、Logo 及品牌标识的权益归 LuminousChenXi 团队所有，未获授权不得用于商业宣传。',
      '您在本应用中输入的内容及其产生的输出内容的权属，按您所使用的模型服务商的相关条款确定。开发团队不对您的内容主张所有权。',
      '您配置的第三方模型服务（如 OpenAI、Anthropic 等）的名称与商标归其各自所有者所有；本应用与其之间不存在隶属或背书关系。',
      '经云端额度获得的模型输出仅供您个人在应用内正常使用，不得用于训练竞争性模型或批量数据爬取。'
    ]
  },
  {
    key: 'disclaimer',
    content: [
      '本软件按"原样"提供，不附带任何明示或暗示的保证，包括但不限于对适销性、特定用途适用性、不侵权及持续可用性的保证。',
      'AI 生成内容可能不准确、不完整或不适用。您应自行核实重要信息；因依赖 AI 生成内容而产生的任何直接或间接损失，开发团队在法律允许的最大范围内不承担责任。',
      '对于因不可抗力、第三方服务变更或中断、网络故障、您不当配置（如泄露 API Key）等原因导致的服务异常或数据损失，开发团队不承担责任。',
      '在任何情况下，开发团队的累计责任上限（如适用法律强制规定最低标准，则以其为准）不超过您为相关云端服务实际支付的金额（如有）；本应用本体为免费开源软件，不收取许可费用。'
    ]
  },
  {
    key: 'changes',
    content: [
      '我们可能随着版本迭代对本应用的功能、界面与服务能力进行调整、增强或下线。重大变更将通过应用内公告或版本说明告知。',
      '云端服务能力（模型额度、通行证、云同步等）的提供方式与额度规则可能调整；若某项服务终止，我们会尽力提前通知并提供替代方案或数据导出途径。',
      '若您不同意更新后的协议或服务变更，可以停止使用相关服务；继续使用即视为接受变更后的内容。协议文本的版本号会在重大修订时更新。'
    ]
  },
  {
    key: 'disputes',
    content: [
      '中国大陆用户：本协议的订立、履行与解释适用中华人民共和国（不含港澳台地区）法律。因本协议引起的争议，双方应友好协商解决；协商不成的，任何一方可向开发者所在地有管辖权的人民法院提起诉讼。',
      '美国用户：本协议适用您居住地所在州的法律（在不与联邦法律冲突的范围内）。相关消费者权利（包括各州隐私法赋予的权利）不受本协议放弃；各行权方式详见「设置 → 隐私与合规」。',
      '其他地区用户：适用您所在司法辖区的强制性法律规定；本协议未尽事宜以对消费者更有利的强制性规定为准。',
      '本协议部分条款被认定无效的，不影响其余条款的效力。'
    ]
  },
  {
    key: 'dataControl',
    content: [
      '您可以随时停用本应用：卸载即可移除程序本体；本机数据（对话记录、配置、偏好）保留在应用数据目录中，您可以自行访问、备份或彻底删除。',
      '您可以随时在设置中清除本地数据、退出本地账号与辰汐通行证。退出并清除后，本机不再保留可识别您身份的云端令牌。',
      '显示偏好多端同步仅同步界面语言、主题模式与协议同意记录等显示偏好（最小必要），绝不同步聊天记录、记忆、皮套资产、平台凭证或任何密钥；您可以随时在「设置 → 通行证登录」中关闭该开关。',
      '行使上述数据控制权利的方式与隐私处理规则，详见「设置 → 隐私与合规」中的隐私政策全文。'
    ]
  }
]

const sectionIconMap: Record<string, typeof Scale> = {
  serviceNature: Bot,
  accounts: UserCheck,
  conduct: Gavel,
  ip: Copyright,
  disclaimer: ShieldAlert,
  changes: RefreshCw,
  disputes: Scale,
  dataControl: Trash2
}

const sectionIcon = (key: string) => sectionIconMap[key] ?? Scale

/** 分节标题经 i18n 解析（正文段落为固定协议文本，保留原文） */
const viewSections = computed(() =>
  sections.map((s) => ({ ...s, title: t(`terms.sections.${s.key}`) })),
)

const visibleSections = ref<Set<number>>(new Set([0]))
let observer: IntersectionObserver | null = null

onMounted(() => {
  observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        const idx = Number(entry.target.getAttribute('data-section-idx'))
        if (entry.isIntersecting) {
          visibleSections.value.add(idx)
        }
      })
    },
    { threshold: 0.15, rootMargin: '0px 0px -40px 0px' }
  )

  document.querySelectorAll('[data-section-idx]').forEach((el) => {
    observer!.observe(el)
  })
})

onUnmounted(() => {
  observer?.disconnect()
})

const isVisible = (idx: number) => visibleSections.value.has(idx)

/** 从首启向导进入时回退向导；其余情况回设置主页 */
const goBack = (): void => {
  if (route.query.from === 'welcome' && window.history.length > 1) {
    router.back()
  } else {
    router.push('/settings')
  }
}
</script>

<template>
  <div class="lumi-settings-page terms-view">
    <LumiSettingsBackground />
    <header class="lumi-settings-page__header lumi-settings-animate-fade">
      <button class="lumi-settings-page__back" @click="goBack">
        <ArrowLeft :size="18" />
      </button>
      <div>
        <h1 class="lumi-settings-page__title">{{ t('terms.title') }}</h1>
        <p class="lumi-settings-page__subtitle">{{ t('terms.subtitle', { version: TERMS_VERSION }) }}</p>
      </div>
    </header>

    <div class="lumi-settings-page__body">
      <section class="privacy-hero lumi-settings-animate-slide">
        <div class="privacy-hero__content">
          <FileText :size="28" class="privacy-hero__icon" />
          <h2 class="privacy-hero__title">{{ t('terms.hero.title') }}</h2>
          <p class="privacy-hero__desc">{{ t('terms.hero.desc') }}</p>
        </div>
      </section>

      <section class="privacy-intro lumi-settings-animate-slide">
        <p class="privacy-lead">{{ t('terms.lead') }}</p>
        <!-- 法务审阅提示（产品自述文本，正式发布前建议经法务审阅；此行刻意不进 i18n） -->
        <p class="legal-review-note">注：本协议为产品自述文本，正式发布前建议经法务审阅。</p>
      </section>

      <section
        v-for="(section, sIdx) in viewSections"
        :key="section.key"
        :data-section-idx="sIdx"
        :class="['privacy-section', { visible: isVisible(sIdx) }]"
      >
        <h2 class="privacy-section__title">
          <component :is="sectionIcon(section.key)" :size="14" />
          {{ section.title }}
        </h2>
        <p
          v-for="(para, pIdx) in section.content"
          :key="pIdx"
          class="privacy-paragraph"
        >{{ para }}</p>
      </section>

      <section
        :data-section-idx="sections.length"
        :class="['privacy-section', { visible: isVisible(sections.length) }]"
      >
        <h2 class="privacy-section__title">
          <Users :size="14" />
          {{ t('terms.sections.contact') }}
        </h2>
        <p class="privacy-paragraph">{{ t('terms.contact.desc') }}</p>
        <ul class="privacy-list">
          <li>{{ t('terms.contact.githubLabel') }}<a href="https://github.com/LuminousCX/LuomiNest/issues" target="_blank" rel="noopener noreferrer">LuminousCX/LuomiNest</a></li>
          <li>{{ t('terms.contact.homepageLabel') }}<a href="https://github.com/LuminousCX/LuomiNest" target="_blank" rel="noopener noreferrer">github.com/LuminousCX/LuomiNest</a></li>
        </ul>
      </section>
    </div>
  </div>
</template>

<style scoped src="../../styles/views/privacy-view.css"></style>

<style scoped>
/* 背景由 settings-independent-bg.css 独立控制 */

/* 法务审阅小字提示 */
.legal-review-note {
  margin: var(--space-2) 0 0;
  font-size: var(--text-xs);
  color: var(--text-muted);
  opacity: 0.85;
}
</style>
