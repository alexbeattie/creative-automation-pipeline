<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

type AspectRatio = "1:1" | "2:3" | "3:2";

interface ProductRow {
  id: string;
  name: string;
  description: string;
  file: File | null;
  idEdited: boolean;
}

interface BrandProfile {
  id: string;
  name: string;
  version: string;
  voice: string;
  palette: string[];
  must_include: string[];
  must_avoid: string[];
}

interface LocaleProfile {
  locale: string;
  language: string;
  cultural_cues: string[];
  seasonal_context: string;
  aesthetic_keywords: string[];
}

interface LocalizedCopy {
  headline: string;
  subhead: string;
  cta: string;
  language: string;
  source: "user" | "llm";
}

interface Asset {
  product_id: string;
  aspect_ratio: AspectRatio;
  channel: string | null;
  width: number;
  height: number;
  strategy: "generated" | "cropped";
  relative_path: string;
  prompt: string | null;
  copy: LocalizedCopy | null;
}

interface CampaignResult {
  campaign_id: string;
  campaign_name: string;
  brand_profile_id: string;
  brand_profile_version: string;
  created_at: string;
  assets: Asset[];
  warnings: string[];
}

const ALL_RATIOS: AspectRatio[] = ["1:1", "2:3", "3:2"];

function sortBrandsWithSelectedFirst(
  items: BrandProfile[],
  selectedBrandId: string
): BrandProfile[] {
  const deduped = Array.from(new Map(items.map((item) => [item.id, item])).values());
  return deduped.sort((a, b) => {
    if (a.id === selectedBrandId) return -1;
    if (b.id === selectedBrandId) return 1;
    return a.name.localeCompare(b.name);
  });
}

function sortLocalesWithSelectedFirst(
  items: LocaleProfile[],
  selectedLocale: string
): LocaleProfile[] {
  const deduped = Array.from(new Map(items.map((item) => [item.locale, item])).values());
  return deduped.sort((a, b) => {
    if (a.locale === selectedLocale) return -1;
    if (b.locale === selectedLocale) return 1;
    return a.locale.localeCompare(b.locale);
  });
}

function blankProductRow(): ProductRow {
  return {
    id: "",
    name: "",
    description: "",
    file: null,
    idEdited: false,
  };
}

const form = reactive({
  campaign_name: "",
  target_region: "US",
  locale: "en-US",
  brand_profile_id: "default",
  target_audience: "",
  campaign_message: "",
  aspect_ratios: [] as AspectRatio[],
  products: [blankProductRow()] as ProductRow[],
});

const loading = ref(false);
const error = ref<string | null>(null);
const result = ref<CampaignResult | null>(null);
const brands = ref<BrandProfile[]>([
  {
    id: "default",
    name: "Default",
    version: "1.0.0",
    voice: "Clean, modern, understated. Confident without exaggeration.",
    palette: [],
    must_include: [],
    must_avoid: [],
  },
]);
const locales = ref<LocaleProfile[]>([
  {
    locale: "en-US",
    language: "English",
    cultural_cues: [],
    seasonal_context: "",
    aesthetic_keywords: [],
  },
]);
const expandedPrompt = ref<Record<string, boolean>>({});

const selectedBrand = computed<BrandProfile | null>(
  () => brands.value.find((b) => b.id === form.brand_profile_id) ?? null
);

const selectedLocale = computed<LocaleProfile | null>(
  () => locales.value.find((l) => l.locale === form.locale) ?? null
);

const canSubmit = computed(
  () =>
    !loading.value &&
    form.campaign_name.trim() &&
    form.campaign_message.trim() &&
    form.aspect_ratios.length > 0 &&
    form.products.length > 0 &&
    form.products.every(
      (p) => p.id.trim() && p.name.trim() && p.description.trim()
    )
);

function slugify(s: string): string {
  return s
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

function addProduct() {
  form.products.push(blankProductRow());
}

function removeProduct(i: number) {
  form.products.splice(i, 1);
}

function onFileChange(i: number, e: Event) {
  const input = e.target as HTMLInputElement;
  form.products[i].file = input.files?.[0] ?? null;
}

function onNameInput(i: number) {
  if (!form.products[i].idEdited) {
    form.products[i].id = slugify(form.products[i].name);
  }
}

function onIdInput(i: number) {
  form.products[i].idEdited = form.products[i].id.trim().length > 0;
}

function toggleRatio(r: AspectRatio) {
  const idx = form.aspect_ratios.indexOf(r);
  if (idx >= 0) form.aspect_ratios.splice(idx, 1);
  else form.aspect_ratios.push(r);
}

async function buildIdempotencyKey(): Promise<string> {
  const payload = {
    campaign_name: form.campaign_name.trim(),
    target_region: form.target_region.trim(),
    locale: form.locale,
    brand_profile_id: form.brand_profile_id,
    target_audience: form.target_audience.trim(),
    campaign_message: form.campaign_message.trim(),
    aspect_ratios: [...form.aspect_ratios],
    products: form.products.map((p) => ({
      id: slugify(p.id || p.name),
      name: p.name.trim(),
      description: p.description.trim(),
      file: p.file
        ? {
            name: p.file.name,
            size: p.file.size,
            last_modified: p.file.lastModified,
            type: p.file.type,
          }
        : null,
    })),
  };

  const encoded = new TextEncoder().encode(JSON.stringify(payload));
  const digest = await crypto.subtle.digest("SHA-256", encoded);
  const hash = Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
  return `ui-${hash.slice(0, 24)}`;
}

async function loadProfiles() {
  try {
    const [brandsRes, localesRes] = await Promise.all([
      fetch("/api/brands"),
      fetch("/api/locales"),
    ]);
    if (brandsRes.ok) {
      const fetchedBrands = (await brandsRes.json()) as BrandProfile[];
      brands.value = sortBrandsWithSelectedFirst(fetchedBrands, form.brand_profile_id);
    }
    if (localesRes.ok) {
      const fetchedLocales = (await localesRes.json()) as LocaleProfile[];
      locales.value = sortLocalesWithSelectedFirst(fetchedLocales, form.locale);
    }
  } catch (e) {
    console.warn("could not load brand/locale profiles", e);
  }
}

onMounted(loadProfiles);

async function submit() {
  loading.value = true;
  error.value = null;

  const idempotencyKey = await buildIdempotencyKey();

  const briefPayload = {
    campaign_name: form.campaign_name,
    target_region: form.target_region,
    locale: form.locale,
    brand_profile_id: form.brand_profile_id,
    target_audience: form.target_audience,
    campaign_message: form.campaign_message,
    aspect_ratios: form.aspect_ratios,
    idempotency_key: idempotencyKey,
    products: form.products.map((p) => ({
      id: slugify(p.id || p.name),
      name: p.name,
      description: p.description,
    })),
  };

  const fd = new FormData();
  fd.append("brief", JSON.stringify(briefPayload));
  for (const p of form.products) {
    fd.append(
      "sources",
      p.file ?? new Blob([], { type: "application/octet-stream" }),
      p.file?.name ?? ""
    );
  }

  try {
    const r = await fetch("/api/campaigns", { method: "POST", body: fd });
    if (!r.ok) {
      const text = await r.text();
      throw new Error(`${r.status} ${r.statusText}: ${text}`);
    }
    result.value = (await r.json()) as CampaignResult;
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    loading.value = false;
  }
}

function ratioLabel(r: AspectRatio): string {
  return { "1:1": "Square 1:1", "2:3": "Portrait 2:3", "3:2": "Landscape 3:2" }[
    r
  ];
}

function strategyBadgeClass(s: Asset["strategy"]): string {
  return s === "generated"
    ? "bg-violet-100 text-violet-800 ring-violet-200 dark:bg-violet-950/60 dark:text-violet-300 dark:ring-violet-900"
    : "bg-emerald-100 text-emerald-800 ring-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-300 dark:ring-emerald-900";
}

function togglePrompt(key: string) {
  expandedPrompt.value[key] = !expandedPrompt.value[key];
}
</script>

<template>
  <div class="min-h-screen">
    <header
      class="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900"
    >
      <div class="mx-auto max-w-7xl px-6 py-4">
        <h1 class="text-lg font-semibold tracking-tight">
          Creative Automation Pipeline
        </h1>
        <p class="text-sm text-slate-500 dark:text-slate-400">
          Brief → brand-aware, locale-aware assets in three native ratios.
          Upload a hero photo to crop, or leave blank to generate with AI.
        </p>
      </div>
    </header>

    <main
      class="mx-auto grid max-w-7xl grid-cols-1 gap-8 px-6 py-8 lg:grid-cols-[420px_1fr]"
    >
      <!-- ── LEFT: form ── -->
      <section class="space-y-6">
        <div
          class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900"
        >
          <h2
            class="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400"
          >
            Campaign
          </h2>

          <label class="mb-3 block">
            <span
              class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300"
              >Name</span
            >
            <input
              v-model="form.campaign_name"
              type="text"
              class="w-full rounded-md text-sm"
            />
          </label>

          <label class="mb-3 block">
            <span
              class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300"
              >Brand profile</span
            >
            <select
              v-model="form.brand_profile_id"
              class="w-full rounded-md text-sm"
            >
              <option v-for="b in brands" :key="b.id" :value="b.id">
                {{ b.name }} (v{{ b.version }})
              </option>
            </select>
            <span
              v-if="selectedBrand"
              class="mt-1 block text-xs text-slate-500 dark:text-slate-400"
            >
              Selected brand: {{ selectedBrand.name }} (v{{ selectedBrand.version }})
            </span>
            <span
              v-if="selectedBrand"
              class="mt-1 block text-xs text-slate-500 dark:text-slate-400"
            >
              {{ selectedBrand.voice }}
            </span>
          </label>

          <div class="mb-3 grid grid-cols-2 gap-3">
            <label>
              <span
                class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300"
                >Region</span
              >
              <input
                v-model="form.target_region"
                type="text"
                class="w-full rounded-md text-sm"
              />
            </label>
            <label>
              <span
                class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300"
                >Locale</span
              >
              <select
                v-if="locales.length > 0"
                v-model="form.locale"
                class="w-full rounded-md text-sm"
              >
                <option v-for="l in locales" :key="l.locale" :value="l.locale">
                  {{ l.locale }} ({{ l.language }})
                </option>
              </select>
              <input
                v-else
                v-model="form.locale"
                type="text"
                class="w-full rounded-md text-sm"
              />
              <span
                v-if="selectedLocale"
                class="mt-1 block text-xs text-slate-500 dark:text-slate-400"
              >
                Selected locale: {{ selectedLocale.locale }} ({{ selectedLocale.language }})
              </span>
            </label>
          </div>

          <label class="mb-3 block">
            <span
              class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300"
              >Audience</span
            >
            <input
              v-model="form.target_audience"
              type="text"
              class="w-full rounded-md text-sm"
            />
          </label>

          <label class="mb-3 block">
            <span
              class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300"
              >Campaign message (concept)</span
            >
            <input
              v-model="form.campaign_message"
              type="text"
              class="w-full rounded-md text-sm"
            />
            <span class="mt-1 block text-xs text-slate-500 dark:text-slate-400">
              This is the source concept for the on-image headline. For
              non-English locales, the pipeline can adapt it to the selected
              market when copy localization is enabled.
            </span>
          </label>

          <div>
            <span
              class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300"
              >Aspect ratios</span
            >
            <div class="flex flex-wrap gap-2">
              <label
                v-for="r in ALL_RATIOS"
                :key="r"
                :class="[
                  'inline-flex cursor-pointer select-none items-center gap-2 rounded-lg border px-3 py-2 text-xs font-medium transition',
                  form.aspect_ratios.includes(r)
                    ? 'border-slate-900 bg-slate-900 text-white shadow-sm dark:border-slate-100 dark:bg-slate-100 dark:text-slate-900'
                    : 'border-slate-300 bg-white text-slate-700 hover:border-slate-400 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:border-slate-500 dark:hover:bg-slate-700',
                ]"
              >
                <input
                  type="checkbox"
                  class="sr-only"
                  :checked="form.aspect_ratios.includes(r)"
                  @change="toggleRatio(r)"
                />
                <span
                  :class="[
                    'flex h-4 w-4 shrink-0 items-center justify-center rounded border transition',
                    form.aspect_ratios.includes(r)
                      ? 'border-white bg-white text-slate-900 dark:border-slate-900 dark:bg-slate-900 dark:text-slate-100'
                      : 'border-slate-400 bg-transparent text-transparent dark:border-slate-500',
                  ]"
                  aria-hidden="true"
                >
                  <svg
                    viewBox="0 0 16 16"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2.5"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    class="h-3 w-3"
                  >
                    <path d="M3 8.5l3.5 3.5L13 5" />
                  </svg>
                </span>
                <span>{{ ratioLabel(r) }}</span>
              </label>
            </div>
          </div>
        </div>

        <div
          class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900"
        >
          <div class="mb-4 flex items-center justify-between">
            <h2
              class="text-sm font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400"
            >
              Products
            </h2>
            <button
              type="button"
              class="text-xs font-medium text-slate-700 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white"
              @click="addProduct"
            >
              + Add product
            </button>
          </div>

          <div
            v-for="(p, i) in form.products"
            :key="i"
            class="mb-4 space-y-2 rounded-lg border border-slate-200 p-3 dark:border-slate-800"
          >
            <div class="flex items-center justify-between">
              <span
                class="text-xs font-semibold text-slate-500 dark:text-slate-400"
                >Product {{ i + 1 }}</span
              >
              <button
                v-if="form.products.length > 1"
                type="button"
                class="text-xs text-slate-400 hover:text-rose-600 dark:text-slate-500 dark:hover:text-rose-400"
                @click="removeProduct(i)"
              >
                remove
              </button>
            </div>
            <input
              v-model="p.name"
              @input="onNameInput(i)"
              type="text"
              placeholder="Name"
              class="w-full rounded-md text-sm"
            />
            <input
              v-model="p.id"
              @input="onIdInput(i)"
              type="text"
              placeholder="id (auto from name)"
              class="w-full rounded-md font-mono text-xs"
            />
            <textarea
              v-model="p.description"
              rows="2"
              placeholder="Short description"
              class="w-full rounded-md text-sm"
            />
            <label class="block">
              <span
                class="mb-1 block text-xs text-slate-500 dark:text-slate-400"
              >
                Optional source image (skip = AI generation)
              </span>
              <input
                type="file"
                accept="image/*"
                @change="(e) => onFileChange(i, e)"
                class="block w-full text-xs text-slate-600 file:mr-3 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-slate-700 hover:file:bg-slate-200 dark:text-slate-400 dark:file:bg-slate-800 dark:file:text-slate-200 dark:hover:file:bg-slate-700"
              />
              <span
                v-if="p.file"
                class="mt-1 block text-xs text-emerald-700 dark:text-emerald-400"
              >
                ✓ {{ p.file.name }} (will crop, no AI)
              </span>
            </label>
          </div>
        </div>

        <button
          type="button"
          :disabled="!canSubmit"
          @click="submit"
          class="w-full rounded-md bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white dark:disabled:bg-slate-700 dark:disabled:text-slate-500"
        >
          {{ loading ? "Generating…" : "Generate campaign" }}
        </button>

        <p class="mt-2 text-xs text-slate-500 dark:text-slate-400">
          Re-submitting the exact same brief reuses an auto-generated idempotency
          key, so repeat clicks return instantly instead of spending AI credits again.
        </p>

        <p
          v-if="error"
          class="rounded-md bg-rose-50 p-3 text-sm text-rose-800 dark:bg-rose-950/60 dark:text-rose-300"
        >
          {{ error }}
        </p>
      </section>

      <!-- ── RIGHT: results ── -->
      <section>
        <div
          v-if="!result && !loading"
          class="flex h-full min-h-[400px] items-center justify-center rounded-xl border-2 border-dashed border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900/50"
        >
          <p class="text-sm text-slate-400 dark:text-slate-500">
            Results will appear here.
          </p>
        </div>

        <div
          v-else-if="loading && !result"
          class="flex h-full min-h-[400px] items-center justify-center rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900"
        >
          <div class="text-center">
            <div
              class="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-2 border-slate-300 border-t-slate-900 dark:border-slate-700 dark:border-t-slate-100"
            ></div>
            <p class="text-sm text-slate-500 dark:text-slate-400">
              Running pipeline…
            </p>
            <p class="mt-1 text-xs text-slate-400 dark:text-slate-500">
              AI generation can take 10-30 seconds per image.
            </p>
          </div>
        </div>

        <div v-else-if="result" class="space-y-4">
          <div
            v-if="loading"
            class="rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900 dark:border-sky-900/70 dark:bg-sky-950/40 dark:text-sky-200"
          >
            <div class="flex items-center gap-3">
              <div
                class="h-4 w-4 animate-spin rounded-full border-2 border-sky-300 border-t-sky-700 dark:border-sky-800 dark:border-t-sky-200"
              ></div>
              <div>
                <p class="font-medium">Generating updated assets...</p>
                <p class="text-xs text-sky-700 dark:text-sky-300">
                  Keeping the previous results visible until the new campaign run finishes.
                </p>
              </div>
            </div>
          </div>

          <div
            class="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"
          >
            <div class="flex items-baseline justify-between">
              <div>
                <p class="text-sm font-semibold">{{ result.campaign_name }}</p>
                <p class="font-mono text-xs text-slate-500 dark:text-slate-400">
                  {{ result.campaign_id }}
                </p>
              </div>
              <p class="text-xs text-slate-500 dark:text-slate-400">
                {{ result.assets.length }} assets ·
                {{ result.warnings.length }} warnings
              </p>
            </div>
            <p class="mt-2 text-xs text-slate-500 dark:text-slate-400">
              Brand:
              <span class="font-medium text-slate-700 dark:text-slate-200">{{
                result.brand_profile_id
              }}</span>
              <span v-if="result.brand_profile_version">
                · v{{ result.brand_profile_version }}</span
              >
            </p>
            <div
              v-if="result.warnings.length"
              class="mt-3 space-y-1 rounded-md bg-amber-50 p-3 text-xs text-amber-800 dark:bg-amber-950/60 dark:text-amber-300"
            >
              <p v-for="(w, i) in result.warnings" :key="i">⚠ {{ w }}</p>
            </div>
          </div>

          <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <figure
              v-for="a in result.assets"
              :key="a.relative_path"
              class="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900"
            >
              <img
                :src="`/api/assets/${a.relative_path}`"
                :alt="`${a.product_id} ${a.aspect_ratio}`"
                class="block w-full bg-slate-100 object-contain dark:bg-slate-800"
                loading="lazy"
              />
              <figcaption
                class="space-y-2 border-t border-slate-100 px-3 py-2 text-xs dark:border-slate-800"
              >
                <div class="flex items-center justify-between">
                  <div>
                    <p class="font-medium text-slate-700 dark:text-slate-200">
                      {{ a.product_id }}
                    </p>
                    <p class="text-slate-500 dark:text-slate-400">
                      {{ a.aspect_ratio }} · {{ a.width }}×{{ a.height }}
                      <span v-if="a.channel"> · {{ a.channel }}</span>
                    </p>
                  </div>
                  <span
                    :class="[
                      'rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ring-1',
                      strategyBadgeClass(a.strategy),
                    ]"
                    >{{ a.strategy }}</span
                  >
                </div>

                <div
                  v-if="a.copy"
                  class="rounded-md bg-slate-50 p-2 dark:bg-slate-800/60"
                >
                  <p
                    class="text-[10px] uppercase tracking-wider text-slate-500 dark:text-slate-400"
                  >
                    Copy ({{ a.copy.source }} · {{ a.copy.language }})
                  </p>
                  <p class="font-medium text-slate-800 dark:text-slate-100">
                    {{ a.copy.headline }}
                  </p>
                  <p
                    v-if="a.copy.subhead"
                    class="text-slate-600 dark:text-slate-300"
                  >
                    {{ a.copy.subhead }}
                  </p>
                  <p
                    v-if="a.copy.cta"
                    class="text-[10px] uppercase tracking-wider text-slate-500 dark:text-slate-400"
                  >
                    CTA: {{ a.copy.cta }}
                  </p>
                </div>

                <div v-if="a.prompt" class="text-[11px]">
                  <button
                    type="button"
                    class="text-slate-500 underline-offset-2 hover:underline dark:text-slate-400"
                    @click="togglePrompt(a.relative_path)"
                  >
                    {{
                      expandedPrompt[a.relative_path]
                        ? "hide prompt"
                        : "show prompt"
                    }}
                  </button>
                  <pre
                    v-if="expandedPrompt[a.relative_path]"
                    class="mt-1 max-h-64 overflow-auto whitespace-pre-wrap rounded bg-slate-50 p-2 font-mono text-[10px] leading-relaxed text-slate-700 dark:bg-slate-800/60 dark:text-slate-200"
                    >{{ a.prompt }}</pre
                  >
                </div>
              </figcaption>
            </figure>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>
