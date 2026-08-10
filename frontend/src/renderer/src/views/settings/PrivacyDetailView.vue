<script setup lang="ts">
import { useRouter } from 'vue-router'
import {
  ArrowLeft,
  Shield,
  Database,
  HardDrive,
  Wifi,
  Puzzle,
  UserCheck,
  Lock,
  Users,
  Globe,
  FileText,
  Mail,
  BookOpen,
  FileCheck
} from 'lucide-vue-next'
import { ref, onMounted, onUnmounted } from 'vue'
import LumiSettingsBackground from '../../components/settings-detail/LumiSettingsBackground.vue'
import '../../styles/views/settings-independent-bg.css'

const router = useRouter()

const sections = [
  {
    title: '数据收集',
    content: [
      'LuomiNest 优先采用本地化数据处理策略。您的对话记录、个人设置和偏好数据默认存储在本地设备上。',
      '当您使用在线 AI 模型服务时，您的对话内容将通过加密连接传输至相应的模型提供商（如 OpenAI、Anthropic 等），以获取推理结果。传输完成后，对话内容不会在我们的服务器上保留副本。',
      '我们不会收集您的个人身份信息、地理位置、设备指纹或浏览历史。',
      '根据《人工智能拟人化互动服务管理暂行办法》的要求，我们在您首次使用时会明确告知您正在与 AI 系统交互，而非真人，确保您对自身交互对象有清晰的认知。'
    ]
  },
  {
    title: '数据存储',
    content: [
      '所有用户数据（包括聊天记录、配置文件、角色数据等）默认存储在您的本地设备中。',
      '数据库文件使用 SQLite 格式存储，位于应用数据目录下。您可以随时通过文件管理器访问或删除这些数据。',
      '如果您启用了端到端加密功能，本地存储的数据将使用 AES-256 加密算法进行保护。',
      '根据《个人信息保护法》第二十一条关于个人信息保存期限的规定，我们仅在实现处理目的所必需的最短时间内保留您的个人信息。超出保留期限后，系统将自动删除或进行匿名化处理。'
    ]
  },
  {
    title: '数据传输',
    content: [
      '与外部服务的通信均通过 HTTPS/TLS 加密连接进行。',
      '当您连接第三方消息平台（如 QQ、微信、Discord 等）时，仅传输必要的消息内容，不会上传本地存储的其他数据。',
      'TTS 语音合成服务：使用在线引擎（如 Edge TTS）时，待合成的文本内容将发送至对应服务提供商。',
      '依据《数据安全法》第三十一条及《个人信息出境标准合同办法》的相关要求，LuomiNest 默认不进行任何跨境数据传输。如确需向境外提供个人信息，我们将严格依法履行安全评估、标准合同备案等法定义务。'
    ]
  },
  {
    title: '第三方服务',
    content: [
      'AI 模型服务：当您配置并使用第三方 AI 模型时，需遵守相应服务提供商的隐私政策。我们建议您在使用前阅读相关条款。',
      '消息平台：连接 QQ、微信、Discord 等平台时，需授权相应的机器人或 API 访问权限。我们仅请求完成核心功能所需的最小权限。',
      '扩展市场：从市场安装的第三方扩展/插件受其各自隐私政策约束。请在安装前确认扩展的可信度。',
      '根据 2025 年 11 月更新的苹果《App 审核指南》第 5.1.2(i) 条精神，任何涉及向第三方 AI 服务传输用户数据的行为，均须事先公开说明并获得用户明确授权。LuomiNest 已在各模型配置入口提供清晰的授权提示。'
    ]
  },
  {
    title: '用户权利',
    content: [
      '访问权：您可以随时查看存储在本地的所有数据。依据 GDPR 第 15 条及《个人信息保护法》第四章之规定，我们保障您对个人信息的知情权与访问权。',
      '删除权：您可以随时删除任何本地数据，包括对话记录、角色配置和应用设置。GDPR 第 17 条"被遗忘权"及《个人信息保护法》第四十七条均保障此项权利。',
      '导出权（数据可携权）：您可以导出您的对话记录和配置数据。GDPR 第 20 条明确赋予数据主体"数据可携权"。',
      '控制权：您可以选择禁用在线服务、限制数据传输范围，或完全使用离线模式运行应用。',
      '撤回同意权：依据《个人信息保护法》第十五条，您有权撤回此前作出的同意。撤回不影响撤回前基于同意已进行的处理活动的效力。',
      '根据《人工智能拟人化互动服务管理暂行办法》第十六条，您有权复制或删除与 AI 的全部历史交互记录，系统已内置一键操作功能。'
    ]
  },
  {
    title: '安全措施',
    content: [
      '所有网络通信均使用 TLS 1.2+ 加密。',
      '敏感配置（如 API 密钥）使用系统级安全存储（Windows Credential Manager / macOS Keychain）进行保护。',
      '应用支持启动密码保护，防止未授权访问。',
      '日志文件中不记录任何敏感信息（API 密钥、密码、对话内容等）。',
      '依据《网络安全法》第二十一条关于网络安全等级保护制度的要求，LuomiNest 在架构设计阶段即融入安全理念，实施数据分类分级管理、访问控制、安全审计等多层防护措施。',
      '《人工智能拟人化互动服务管理暂行办法》第二十条要求服务提供者采用数据加密和访问控制措施保护用户交互数据。LuomiNest 的 AES-256 加密方案与该项要求完全对齐。'
    ]
  },
  {
    title: '未成年人保护',
    content: [
      'LuomiNest 严格遵守各司法管辖区的未成年人保护法规。本应用不面向 13 周岁以下的未成年人提供服务。',
      '对于 14 周岁以下的用户，我们要求取得监护人的明确同意后方可使用本应用的拟人化互动功能。此规定直接对应《人工智能拟人化互动服务管理暂行办法》第十四条及《个人信息保护法》第三十一条。',
      '本应用严禁向未成年人提供虚拟伴侣、虚拟亲属等虚拟亲密关系服务。该禁令源自《人工智能拟人化互动服务管理暂行办法》第八条第（四）项的明确规定。',
      '我们提供未成年人模式，支持监护人管控使用行为、限制使用时长，并在检测到极端情绪时进行及时干预。此设计响应了《人工智能拟人化互动服务管理暂行办法》第十八条关于防沉迷与极端情绪干预的要求。',
      '参考加州 SB 243 法案（全美首部 AI 伴侣聊天机器人法）的立法精神，系统内置定时 AI 身份提醒机制，确保未成年用户始终保持对交互对象属性的清醒认知。'
    ]
  },
  {
    title: '法律法规依据',
    content: [
      'LuomiNest 的设计与运营遵循以下法律法规框架，确保在各主要司法管辖区的合规性：',
      '《中华人民共和国网络安全法》（2017年6月1日施行）——确立网络安全等级保护制度，规范网络运营者的数据安全义务，是 LuomiNest 安全架构设计的顶层法律依据。',
      '《中华人民共和国数据安全法》（2021年9月1日施行）——建立数据分类分级保护制度，明确数据处理活动的安全保护义务，规范数据出境安全管理。',
      '《中华人民共和国个人信息保护法》（2021年11月1日施行）——确立"告知-同意"为核心的个人信息处理规则，赋予个人知情权、决定权、查阅复制权、删除权等完整权利体系。',
      '《生成式人工智能服务管理暂行办法》（2023年8月15日施行）——规范生成式 AI 服务的内容治理、训练数据合规、内容标识等要求，是 LuomiNest AI 对话功能的基础合规依据。',
      '《人工智能拟人化互动服务管理暂行办法》（2026年7月15日施行）——我国首部针对 AI 拟人化互动服务的专门立法，由网信办等五部门联合发布，对 AI 伴侣类应用提出未成年人保护、情感操纵禁止、AI 身份披露、交互数据保护等专项要求。',
      '《人工智能生成合成内容标识办法》（2025年9月1日施行）——要求对所有 AI 生成合成内容进行显著标识，LuomiNest 在 AI 生成的图片、音频等内容中严格遵循标识义务。'
    ]
  },
  {
    title: '合规声明与免责',
    content: [
      'LuomiNest 作为开源项目，遵循项目 LICENSE 中声明的许可协议。本软件按"原样"提供，不提供任何明示或暗示的保证或担保，包括但不限于对适销性、特定用途适用性的保证。',
      'LuomiNest 采用本地优先架构，默认情况下所有数据均在用户设备上处理和存储，不通过 LuomiNest 自有服务器中转任何用户数据。因此，LuomiNest 团队不充当《个人信息保护法》意义上的"个人信息处理者"角色，各模型服务提供商在其服务范围内承担相应的数据处理者责任。',
      '用户在使用第三方 AI 模型服务时，应自行评估并遵守该服务商的用户协议和隐私政策。因使用第三方服务产生的数据保护责任，由相应服务提供商承担。',
      'LuomiNest 不对因用户自行配置第三方服务、安装第三方扩展/插件而导致的数据泄露或安全事件承担责任。',
      '根据《人工智能拟人化互动服务管理暂行办法》第八条，AI 拟人化互动服务提供者不得通过情感操纵等方式诱导用户作出不合理决策，不得过度迎合用户、诱导情感依赖或沉迷。LuomiNest 在系统提示词层面已内置相关安全约束。',
      '本隐私政策不构成法律建议。如有法律疑问，请咨询专业法律人士。'
    ]
  },
  {
    title: '各地区合规说明',
    content: [],
    regions: [
      {
        name: '中国大陆',
        law: '《人工智能拟人化互动服务管理暂行办法》（2026年7月15日施行）',
        items: [
          '本办法由国家网信办等五部门联合发布，是我国首部针对 AI 拟人化互动服务的专门立法。',
          '严禁向未成年人提供虚拟亲属、虚拟伴侣等虚拟亲密关系服务。向不满 14 周岁未成年人提供其他拟人化互动服务的，应当取得监护人同意。',
          '禁止通过情感操纵等方式诱导用户作出不合理决策，禁止过度迎合用户、诱导情感依赖或沉迷。',
          '用户交互数据具有敏感性和私密性，除法定情形或用户同意外，不得向第三方提供。严格限制敏感个人信息用于模型训练。',
          '服务提供者须向用户明确披露其 AI 属性，防止用户产生与真人对话的认知混淆。',
          '当用户出现极端情绪时需及时干预，并提醒用户控制使用时长，防范沉迷与情感依赖。',
          '服务提供者应当建立投诉举报机制，及时受理并处理用户关于拟人化互动服务的投诉和举报。'
        ]
      },
      {
        name: '欧盟 / 欧洲经济区',
        law: 'GDPR（通用数据保护条例）+ EU AI Act（人工智能法案）',
        items: [
          'LuomiNest 在欧盟地区的运营同时受 GDPR 和 EU AI Act 的约束。',
          '根据 EU AI Act 第 50 条，AI 伴侣类应用被归类为"有限风险"（Limited Risk）类别，须履行透明度义务：明确告知用户其正在与 AI 交互，而非真人。',
          'GDPR 要求对用户对话数据等敏感信息实施严格保护，包括数据最小化原则、明确的法律基础、以及数据保护影响评估（DPIA）义务。',
          '欧盟用户享有完整的数据主体权利：访问权（Art.15）、删除权（Art.17）、数据可携权（Art.20）、反对权（Art.21）。',
          '2025年5月，意大利数据保护局对 Replika 开出 500 万欧元罚单，原因是违反 GDPR 多项条款。这标志着欧盟对 AI 伴侣类应用的执法力度正在加强。',
          '自 2026 年 8 月起，EU AI Act 的剩余条款将全面生效，违规罚款上限将提升至约 5500 万欧元或全球年营业额的 3%（以较高者为准）。',
          '根据 GDPR 第 6 条，LuomiNest 以"数据主体的同意"（Art.6(1)(a)）及"正当利益"（Art.6(1)(f)）作为数据处理的法律基础。'
        ]
      },
      {
        name: '美国',
        law: '各州 AI 聊天机器人法规（联邦层面尚无统一立法）',
        items: [
          '截至 2026 年初，全美已有 27 个州提出了共 78 项聊天机器人专项法案，AI 聊天机器人治理成为美国立法最活跃的领域。',
          '加州 SB 243（2026年1月1日生效）：全美首部 AI 伴侣聊天机器人法，要求运营商对已知未成年用户每 3 小时进行一次 AI 身份提醒，并建立自杀意念检测和危机资源转介机制。该法案首次赋予消费者私人诉权。',
          '纽约州《人工智能伴随模型法》：要求 AI 伴侣系统必须能够检测并处理自杀意念或自残表达，将用户推荐至 988 Lifeline 等危机服务。',
          '联邦贸易委员会（FTC）已对多家 AI 伴侣产品展开调查，重点关注数据收集实践和对未成年人的潜在危害。',
          'LuomiNest 作为本地运行的桌面应用，不直接收集用户数据上传至云端，但我们仍建议美国用户遵守所在州的相关法规。',
          '加州消费者隐私法（CCPA/CPRA）赋予加州居民知情权、删除权和选择退出权。LuomiNest 的本地存储架构天然满足 CCPA 对"不出售"用户数据的要求。'
        ]
      },
      {
        name: '日本',
        law: '《个人信息保护法》（APPI）2026年修订版',
        items: [
          '日本于 2026 年 4 月提交了 APPI 修订法案，预计自公布之日起 2 年内施行，是近年来最大规模的修订。',
          '16 岁以下未成年人的个人信息处理将以法定代理人为同意对象，并放宽了未成年人信息停止利用的请求要件。',
          '人脸特征等生物识别信息被纳入严格管理范畴，强制处理者公示相关处理事项，禁止通过退出制（opt-out）向第三方提供。',
          '新增"统计信息作成"同意豁免：明确 AI 开发中使用个人数据的合规路径，但仍需遵守权利侵害风险评估要求。',
          '引入课征金制度：针对营利型、大规模恶意违法行为，责令缴纳相当于违法所得的课征金，并大幅提升刑事处罚力度。',
          'LuomiNest 的本地化数据存储策略与日本 APPI 的数据最小化原则高度契合。'
        ]
      },
      {
        name: '韩国',
        law: '《人工智能基本法》（2025年1月施行）+ 《个人信息保护法》（PIPA）',
        items: [
          '韩国于 2025 年 1 月正式施行《人工智能基本法》，成为亚洲首批建立 AI 综合立法框架的国家之一。',
          '该法将 AI 服务按风险等级分为"重大影响 AI"和"一般 AI"两类，AI 伴侣类应用通常归入一般风险类别，但仍须履行透明度与安全性基本义务。',
          '韩国 PIPA 对个人信息保护标准极为严格，要求数据处理者获得用户明确同意，并在数据收集时告知处理目的、保存期限等关键信息。',
          '韩国放送通信委员会（KCC）有权对违规企业处以最高全球营业额 3% 的罚款。',
          'LuomiNest 的本地优先架构与韩国 PIPA 强调的数据最小化和用户同意原则高度一致。'
        ]
      }
    ]
  },
  {
    title: '政策更新',
    content: [
      '我们可能会不时更新本隐私政策。重大变更将在应用内以通知形式告知用户。',
      '当法律法规发生修订（如《人工智能拟人化互动服务管理暂行办法》配套细则出台），我们将及时对照新规调整本政策内容，确保 LuomiNest 持续合规。',
      '本隐私政策的最近更新日期为 2026 年 7 月。'
    ]
  }
]

const sectionIconMap: Record<string, typeof Shield> = {
  '数据收集': Database,
  '数据存储': HardDrive,
  '数据传输': Wifi,
  '第三方服务': Puzzle,
  '用户权利': UserCheck,
  '安全措施': Lock,
  '未成年人保护': Users,
  '法律法规依据': BookOpen,
  '合规声明与免责': FileCheck,
  '各地区合规说明': Globe,
  '政策更新': FileText
}

const sectionIcon = (title: string) => sectionIconMap[title] ?? Shield

const regionSection = sections.find((s) => s.regions)
const regionCount = regionSection?.regions?.length ?? 0

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
</script>

<template>
  <div class="lumi-settings-page privacy-view">
    <LumiSettingsBackground />
    <header class="lumi-settings-page__header lumi-settings-animate-fade">
      <button class="lumi-settings-page__back" @click="router.push('/settings')">
        <ArrowLeft :size="18" />
      </button>
      <div>
        <h1 class="lumi-settings-page__title">隐私与合规</h1>
        <p class="lumi-settings-page__subtitle">LuomiNest 的数据保护政策与法律法规合规说明</p>
      </div>
    </header>

    <div class="lumi-settings-page__body">
      <section class="lumi-settings-hero lumi-settings-animate-slide">
        <div class="lumi-settings-hero__content">
          <Shield :size="28" class="lumi-settings-hero__icon" />
          <h2 class="lumi-settings-hero__title">隐私优先 · 合规为本</h2>
          <p class="lumi-settings-hero__desc">
            LuomiNest 由 LuminousChenXi 团队开发。我们深知隐私的重要性，致力于保护用户的数据安全与法律合规。
            本页面详细说明了本应用如何收集、使用、存储和保护您的信息，以及我们在各主要司法管辖区的法律法规合规情况。
          </p>
          <div class="lumi-settings-hero__stats">
            <div class="lumi-settings-hero__stat">
              <span class="lumi-settings-hero__stat-value">{{ sections.length }}</span>
              <span class="lumi-settings-hero__stat-label">核心原则</span>
            </div>
            <div class="lumi-settings-hero__divider"></div>
            <div class="lumi-settings-hero__stat">
              <span class="lumi-settings-hero__stat-value">{{ regionCount }}</span>
              <span class="lumi-settings-hero__stat-label">合规地区</span>
            </div>
            <div class="lumi-settings-hero__divider"></div>
            <div class="lumi-settings-hero__stat">
              <span class="lumi-settings-hero__stat-value">AES-256</span>
              <span class="lumi-settings-hero__stat-label">加密标准</span>
            </div>
          </div>
        </div>
      </section>

      <section class="privacy-intro lumi-settings-animate-slide">
        <p class="privacy-lead">
          LuomiNest 优先采用本地化数据处理策略，默认将对话记录、个人设置和偏好数据保存在您的本地设备上。
          当您使用在线服务时，数据通过加密连接传输，且不会在 LuomiNest 服务器上保留副本。
        </p>
      </section>

      <section
        v-for="(section, sIdx) in sections"
        :key="section.title"
        :data-section-idx="sIdx"
        :class="['privacy-section', { visible: isVisible(sIdx) }]"
      >
        <h2 class="privacy-section__title">
          <component :is="sectionIcon(section.title)" :size="14" />
          {{ section.title }}
        </h2>
        <p
          v-for="(para, pIdx) in section.content"
          :key="pIdx"
          class="privacy-paragraph"
        >{{ para }}</p>
        <div v-if="section.regions" class="privacy-region-grid">
          <div v-for="region in section.regions" :key="region.name" class="privacy-region-card">
            <h3 class="privacy-region__name">{{ region.name }}</h3>
            <p class="privacy-region__law">{{ region.law }}</p>
            <ul class="privacy-list">
              <li v-for="(item, iIdx) in region.items" :key="iIdx">{{ item }}</li>
            </ul>
          </div>
        </div>
      </section>

      <section
        :data-section-idx="sections.length"
        :class="['privacy-section privacy-contact-card', { visible: isVisible(sections.length) }]"
      >
        <h2 class="privacy-section__title">
          <Mail :size="14" />
          联系我们
        </h2>
        <p class="privacy-paragraph">如果您对本隐私政策有任何疑问、建议或投诉，请通过以下方式联系我们：</p>
        <ul class="privacy-list">
          <li>GitHub Issues：<a href="https://github.com/LuminousCX/LuomiNest/issues" target="_blank" rel="noopener noreferrer">LuminousCX/LuomiNest</a></li>
          <li>项目主页：<a href="https://github.com/LuminousCX/LuomiNest" target="_blank" rel="noopener noreferrer">github.com/LuminousCX/LuomiNest</a></li>
        </ul>
      </section>
    </div>
  </div>
</template>

<style scoped src="../../styles/views/privacy-view.css"></style>

<style scoped>
/* 背景由 settings-independent-bg.css 独立控制 */
</style>
