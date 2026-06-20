<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ArrowLeft } from 'lucide-vue-next'
import { ref, onMounted, onUnmounted } from 'vue'

const router = useRouter()

const sections = [
  {
    title: '数据收集',
    content: [
      'LuomiNest 优先采用本地化数据处理策略。您的对话记录、个人设置和偏好数据默认存储在本地设备上。',
      '当您使用在线 AI 模型服务时，您的对话内容将通过加密连接传输至相应的模型提供商（如 OpenAI、Anthropic 等），以获取推理结果。传输完成后，对话内容不会在我们的服务器上保留副本。',
      '我们不会收集您的个人身份信息、地理位置、设备指纹或浏览历史。'
    ]
  },
  {
    title: '数据存储',
    content: [
      '所有用户数据（包括聊天记录、配置文件、角色数据等）默认存储在您的本地设备中。',
      '数据库文件使用 SQLite 格式存储，位于应用数据目录下。您可以随时通过文件管理器访问或删除这些数据。',
      '如果您启用了端到端加密功能，本地存储的数据将使用 AES-256 加密算法进行保护。'
    ]
  },
  {
    title: '数据传输',
    content: [
      '与外部服务的通信均通过 HTTPS/TLS 加密连接进行。',
      '当您连接第三方消息平台（如 QQ、微信、Discord 等）时，仅传输必要的消息内容，不会上传本地存储的其他数据。',
      'TTS 语音合成服务：使用在线引擎（如 Edge TTS）时，待合成的文本内容将发送至对应服务提供商。'
    ]
  },
  {
    title: '第三方服务',
    content: [
      'AI 模型服务：当您配置并使用第三方 AI 模型时，需遵守相应服务提供商的隐私政策。我们建议您在使用前阅读相关条款。',
      '消息平台：连接 QQ、微信、Discord 等平台时，需授权相应的机器人或 API 访问权限。我们仅请求完成核心功能所需的最小权限。',
      '扩展市场：从市场安装的第三方扩展/插件受其各自隐私政策约束。请在安装前确认扩展的可信度。'
    ]
  },
  {
    title: '用户权利',
    content: [
      '访问权：您可以随时查看存储在本地的所有数据。',
      '删除权：您可以随时删除任何本地数据，包括对话记录、角色配置和应用设置。',
      '导出权：您可以导出您的对话记录和配置数据。',
      '控制权：您可以选择禁用在线服务、限制数据传输范围，或完全使用离线模式运行应用。'
    ]
  },
  {
    title: '安全措施',
    content: [
      '所有网络通信均使用 TLS 1.2+ 加密。',
      '敏感配置（如 API 密钥）使用系统级安全存储（Windows Credential Manager / macOS Keychain）进行保护。',
      '应用支持启动密码保护，防止未授权访问。',
      '日志文件中不记录任何敏感信息（API 密钥、密码、对话内容等）。'
    ]
  },
  {
    title: '未成年人保护',
    content: [
      'LuomiNest 严格遵守各司法管辖区的未成年人保护法规。本应用不面向 13 周岁以下的未成年人提供服务。',
      '对于 14 周岁以下的用户，我们要求取得监护人的明确同意后方可使用本应用的拟人化互动功能。',
      '本应用严禁向未成年人提供虚拟伴侣、虚拟亲属等虚拟亲密关系服务。',
      '我们提供未成年人模式，支持监护人管控使用行为、限制使用时长，并在检测到极端情绪时进行及时干预。'
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
          '当用户出现极端情绪时需及时干预，并提醒用户控制使用时长，防范沉迷与情感依赖。'
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
          '自 2026 年 8 月起，EU AI Act 的剩余条款将全面生效，违规罚款上限将提升至约 5500 万欧元。'
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
          'LuomiNest 作为本地运行的桌面应用，不直接收集用户数据上传至云端，但我们仍建议美国用户遵守所在州的相关法规。'
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
      }
    ]
  },
  {
    title: '政策更新',
    content: [
      '我们可能会不时更新本隐私政策。重大变更将在应用内以通知形式告知用户。',
      '本隐私政策的最近更新日期为 2026 年 6 月。'
    ]
  }
]

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
  <div class="privacy-detail-view">
    <div class="privacy-header animate-fade-in">
      <button class="back-btn" @click="router.push('/settings')">
        <ArrowLeft :size="18" />
      </button>
      <div>
        <h1 class="page-title">用户隐私政策</h1>
        <p class="page-subtitle">LuomiNest 如何保护您的数据与隐私</p>
      </div>
    </div>

    <div class="privacy-body">
      <article class="privacy-document animate-slide-up">
        <p class="doc-lead">
          LuomiNest（以下简称"本应用"）由 LuminousChenXi 团队开发。
          我们深知隐私的重要性，致力于保护用户的数据安全。
          本隐私政策详细说明了本应用如何收集、使用、存储和保护您的信息。
        </p>

        <section
          v-for="(section, sIdx) in sections"
          :key="section.title"
          :data-section-idx="sIdx"
          :class="['doc-section', { visible: isVisible(sIdx) }]"
        >
          <h2 class="doc-h2">{{ section.title }}</h2>
          <p
            v-for="(para, pIdx) in section.content"
            :key="pIdx"
            class="doc-paragraph"
          >{{ para }}</p>
          <div v-if="section.regions" class="region-grid">
            <div v-for="region in section.regions" :key="region.name" class="region-card">
              <h3 class="region-name">{{ region.name }}</h3>
              <p class="region-law">{{ region.law }}</p>
              <ul class="doc-list">
                <li v-for="(item, iIdx) in region.items" :key="iIdx">{{ item }}</li>
              </ul>
            </div>
          </div>
        </section>

        <section
          :data-section-idx="sections.length"
          :class="['doc-section', { visible: isVisible(sections.length) }]"
        >
          <h2 class="doc-h2">联系我们</h2>
          <p class="doc-paragraph">如果您对本隐私政策有任何疑问、建议或投诉，请通过以下方式联系我们：</p>
          <ul class="doc-list">
            <li>GitHub Issues：<a href="https://github.com/LuminousCX/LuomiNest/issues" target="_blank" rel="noopener noreferrer">LuminousCX/LuomiNest</a></li>
            <li>项目主页：<a href="https://github.com/LuminousCX/LuomiNest" target="_blank" rel="noopener noreferrer">github.com/LuminousCX/LuomiNest</a></li>
          </ul>
        </section>
      </article>
    </div>
  </div>
</template>

<style scoped>
.privacy-detail-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--workspace-bg);
  overflow: hidden;
}

.privacy-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 28px;
  border-bottom: 1px solid var(--workspace-border);
  flex-shrink: 0;
}

.back-btn {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.back-btn:hover {
  background: var(--workspace-hover);
  color: var(--lumi-primary);
}

.page-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
}

.page-subtitle {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 1px;
}

/* ── Single document container ── */

.privacy-body {
  flex: 1;
  overflow-y: auto;
  padding: 28px 32px 40px;
}

.privacy-document {
  background: var(--workspace-card);
  border-radius: var(--radius-lg);
  padding: 28px 32px 36px;
}

/* ── Lead paragraph ── */

.doc-lead {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.8;
  margin-bottom: 32px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--divider-soft);
}

/* ── Section with scroll-reveal ── */

.doc-section {
  margin-top: 28px;
  padding-top: 4px;
  opacity: 0;
  transform: translateY(16px);
  transition: opacity 0.4s ease-in-out, transform 0.4s ease-in-out;
}

.doc-section.visible {
  opacity: 1;
  transform: translateY(0);
}

/* ── Markdown-like typography ── */

.doc-h2 {
  font-size: 17px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--divider-soft);
  letter-spacing: -0.2px;
}

.doc-paragraph {
  font-size: 13.5px;
  color: var(--text-secondary);
  line-height: 1.85;
  margin-bottom: 10px;
}

.doc-paragraph:last-child {
  margin-bottom: 0;
}

.doc-list {
  padding-left: 22px;
  margin-top: 8px;
}

.doc-list li {
  font-size: 13.5px;
  color: var(--text-secondary);
  line-height: 1.85;
  margin-bottom: 6px;
}

.doc-list a {
  color: var(--lumi-primary);
  text-decoration: none;
  transition: color var(--transition-fast);
}

.doc-list a:hover {
  color: var(--lumi-primary-hover);
  text-decoration: underline;
}

/* ── Regional compliance cards ── */

.region-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-top: 12px;
}

.region-card {
  background: var(--workspace-bg);
  border-radius: var(--radius-md);
  padding: 16px 18px;
}

.region-name {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.region-law {
  font-size: 11px;
  color: var(--lumi-primary);
  font-weight: 500;
  margin-bottom: 10px;
  line-height: 1.5;
}

.region-card .doc-list {
  padding-left: 18px;
  margin-top: 0;
}

.region-card .doc-list li {
  font-size: 12.5px;
  line-height: 1.75;
  margin-bottom: 6px;
}
</style>
