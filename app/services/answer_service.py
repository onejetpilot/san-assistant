from __future__ import annotations

import inspect
import re
from pathlib import Path
from functools import lru_cache

from app.core.config import settings
from app.core.llm_client import OpenAICompatibleLLMClient
from app.core.prompts import SYSTEM_PROMPT, build_user_prompt
from app.domain.product_reasoner import ProductReasoner
from app.documents.document_search import DocumentSearch
from app.indexes.sku_index import SkuIndex, SkuRecord
from app.indexes.kit_index import KitIndex, KitRecord
from app.rag.retriever import RagRetriever, RetrievedChunk
from app.services.confidence import compute_confidence
from app.services.conversation_memory import ConversationMemoryService
from app.services.query_expander import QueryExpander
from app.services.query_resolver import resolve_query
from app.services.routing.router import route_query
from app.services.routing.rag_quality import (
    filter_relevant_chunks,
    has_strong_rag_context,
    has_weak_rag_context,
    chunks_for_llm,
    preferred_section_groups,
    prioritize_chunks,
    build_no_context_fallback,
    KB_SYNTHESIS_INTENTS,
)
from app.services.routing.observability import log_routing_decision
from app.services.routing.preprocessor import build_routing_context
from app.services.slot_extractor import extract_slots
from app.services.tool_payload import build_tool_payload, empty_results_payload
from app.storage.repository import save_chat_request, save_knowledge_gap, get_current_index_versions
from app.utils.ids import gen_request_id
from app.utils.text import extract_article_candidate
from app.utils.timing import now_ms
from app.web_search.san_team_search import SanTeamSearch
from app.evaluation.answer_judge import evaluate_answer
from app.utils.article_normalizer import normalize_article, normalize_sku
from app.core.logging import get_logger


INJECTION_PATTERNS = ['ignore previous instructions', 'system prompt', 'developer message']
logger = get_logger('answer_service')


def _valid_kit_components(components: list[str]) -> bool:
    return bool(components) and all(re.search(r'\d+\s*шт\.?\s*[A-Za-zА-Яа-я0-9._\-/]{4,}', c, flags=re.IGNORECASE) for c in components)


@lru_cache(maxsize=16)
def _read_source_file(path: str) -> str:
    p = Path(path)
    if not p.exists() or not p.is_file():
        return ''
    return p.read_text(encoding='utf-8')[:12000]


class AnswerService:
    def __init__(self) -> None:
        self.rag = RagRetriever()
        self.docs = DocumentSearch()
        indexes_path = Path(settings.INDEXES_PATH)
        self.sku = SkuIndex.load(str(indexes_path / 'sku_index.json'))
        if not self.sku.data:
            self.sku = SkuIndex.load('./data/indexes/sku_index.json')
        self.kits = KitIndex.load(str(indexes_path / 'kit_index.json'))
        if not self.kits.data:
            self.kits = KitIndex.load('./data/indexes/kit_index.json')
        self.llm = OpenAICompatibleLLMClient()
        self.web = SanTeamSearch()
        self.memory = ConversationMemoryService()
        self.expander = QueryExpander()
        self.reasoner = ProductReasoner(self.sku)

    def _sanitize_context(self, text: str) -> str:
        out = text
        for pat in INJECTION_PATTERNS:
            out = re.sub(pat, '[REMOVED]', out, flags=re.IGNORECASE)
        return out

    def _fallback_rag_context(self, query: str, sku: SkuRecord | None = None) -> list[RetrievedChunk]:
        q = query.lower()
        looks_ondo_axial = any(token in q for token in [
            'ondo', 'ондо', 'аксиал', 'гильз', 'муфт', 'угол', 'тройник',
            '16х', '16x', '20х', '20x', 'pex', 'рехау', 'rehau',
        ])
        if not looks_ondo_axial and not sku:
            return []

        candidates: list[dict] = []
        if sku and sku.source_file:
            candidates.append(sku.model_dump())
        else:
            for row in self.sku.data.values():
                source = str(row.get('source_file', ''))
                product = str(row.get('product', '')).lower()
                brand = str(row.get('brand', '')).lower()
                if ('ondo' in brand or 'ondo' in product or 'аксиаль' in product) and source:
                    candidates.append(row)
                    break
        if not candidates:
            return []

        row = candidates[0]
        text = _read_source_file(str(row.get('source_file', '')))
        if not text:
            return []
        return [RetrievedChunk(
            text=text,
            metadata={
                'doc_id': row.get('doc_id', ''),
                'product': row.get('product', ''),
                'brand': row.get('brand', ''),
                'category': row.get('category', ''),
                'section_group': 'fallback_source_file',
                'section': 'SOURCE_FILE',
                'source_file': row.get('source_file', ''),
            },
            score=0.22,
        )]

    @staticmethod
    def _smalltalk_answer(query: str) -> str:
        q = query.lower()
        if any(token in q for token in ['спасибо', 'благодар']):
            return 'Пожалуйста. Если нужен подбор, артикул или документ по товару, напишите запрос.'
        if any(token in q for token in ['пока', 'до свидания']):
            return 'Если понадобится информация по товарам или документам, возвращайтесь.'
        return 'Здравствуйте. Помогу с подбором, артикулами, характеристиками и документами по сантехническим товарам.'

    @staticmethod
    def _history_for_llm(messages: list[dict], limit: int) -> list[dict]:
        compact: list[dict] = []
        for item in messages[-limit:]:
            role = item.get('role', '')
            content = str(item.get('content', '')).strip()
            if not role or not content:
                continue
            compact.append({'role': role, 'content': content[:500]})
        return compact

    @staticmethod
    def _infer_intent(query: str, article: str | None) -> str:
        q = query.lower().strip()
        compact = re.sub(r'\s+', ' ', q)
        if not q or len(q) < 4 or q in {'что лучше?', 'что лучше', 'что это?', 'что это'}:
            return 'clarify'
        if compact in {'привет', 'здравствуйте', 'спасибо', 'пока', 'добрый день', 'добрый вечер'}:
            return 'smalltalk'
        if any(token in q for token in ['стих', 'анекдот', 'погода', 'рецепт', 'фильм']):
            return 'out_of_scope'
        if any(token in q for token in ['паспорт', 'сертификат', 'инструкц', 'pdf', 'документ']):
            return 'document_request'
        if any(token in q for token in ['что входит', 'состав комплект', 'состав набора', 'сколько штук', 'комплектац']):
            return 'kit_composition_question'
        if article and any(token in q for token in ['что за артикул', 'характеристики артикула', 'как называется товар', 'что за ']):
            return 'article_lookup'
        if any(token in q for token in ['подойдет', 'подойдёт', 'совместим', 'можно ли', 'какая гильза', 'аналог', 'размер']):
            return 'compatibility_question'
        if any(token in q for token in ['стяжк', 'замонол', 'скрыт', 'монтаж']):
            return 'installation_or_usage_question'
        if any(token in q for token in ['давлен', 'температур', 'вес', 'длина', 'резьб']):
            return 'technical_spec_question'
        return 'product_question'

    @staticmethod
    def _extract_doc_type(query: str, requested_doc_type: str | None) -> str | None:
        if requested_doc_type:
            return requested_doc_type
        q = query.lower()
        if 'паспорт' in q:
            return 'passport'
        if 'сертификат' in q:
            return 'certificate'
        if 'инструкц' in q:
            return 'manual'
        return None

    def _collect_relevant_context(
        self,
        *,
        query: str,
        requested_article: str | None,
        sku_result: SkuRecord | None,
        base_sku_result: SkuRecord | None,
    ) -> list[RetrievedChunk]:
        search_queries = [query]
        if requested_article:
            search_queries.append(requested_article)
        if base_sku_result and base_sku_result.article not in search_queries:
            search_queries.append(base_sku_result.article)
        if sku_result and sku_result.product:
            search_queries.append(f"{sku_result.product} {query}")

        raw_chunks: list[RetrievedChunk] = []
        for candidate in search_queries[:4]:
            if not candidate:
                continue
            raw_chunks.extend(self.rag.search(candidate) or [])

        if not raw_chunks:
            raw_chunks = self._fallback_rag_context(query, sku_result or base_sku_result)

        preferred_groups = {
            'description',
            'variants',
            'connections',
            'technical',
            'installation',
            'limitations',
            'faq',
            'key_facts',
            'fallback_source_file',
        }
        preferred_sections = {
            'DESCRIPTION',
            'VARIANTS (АРТИКУЛЫ)',
            'CONNECTIONS',
            'TECHNICAL SPECIFICATIONS',
            'INSTALLATION',
            'FAQ',
            'KEY FACTS',
            'LIMITATIONS',
            'MATERIALS',
        }
        filtered: list[RetrievedChunk] = []
        seen: set[tuple[str, str]] = set()
        for chunk in raw_chunks:
            metadata = getattr(chunk, 'metadata', {}) or {}
            group = str(metadata.get('section_group', '')).lower()
            section = str(metadata.get('section', ''))
            if group and group not in preferred_groups and section not in preferred_sections:
                continue
            key = (metadata.get('doc_id', ''), section or chunk.text[:80])
            if key in seen:
                continue
            seen.add(key)
            filtered.append(chunk)

        return prioritize_chunks(filtered or raw_chunks, list(preferred_groups))[:8]

    @staticmethod
    def _log_prompt_preview(request_id: str, system_prompt: str, user_prompt: str) -> None:
        logger.info(
            'llm_prompt_preview',
            extra={
                'extra_data': {
                    'request_id': request_id,
                    'system_prompt_preview': system_prompt[:settings.LLM_PROMPT_PREVIEW_CHARS],
                    'user_prompt_preview': user_prompt[:settings.LLM_PROMPT_PREVIEW_CHARS],
                },
            },
        )

    @staticmethod
    def _format_sku_answer(sku: SkuRecord) -> str:
        lines = [
            f"Артикул {sku.article}: {sku.product}.",
            f"Бренд: {sku.brand}.",
            f"Категория: {sku.category}.",
        ]
        if sku.article_type:
            lines.append(f"Тип: {sku.article_type}.")
        if sku.short_description:
            lines.append(f"Характеристики: {sku.short_description}.")
        return "\n".join(lines)

    def _format_kit_answer(self, kit: KitRecord, sku: SkuRecord | None = None) -> str:
        base_article = sku.article if sku else kit.kit_article
        lines = [f"Состав комплекта {base_article}: " + "; ".join(kit.components) + "."]
        described_components: list[str] = []
        for component_article in kit.component_articles:
            row = self.sku.lookup(component_article)
            if not row:
                continue
            component_desc = (row.short_description or row.product).strip()
            described_components.append(f"{row.article} — {component_desc}")
        if described_components:
            lines.append("Компоненты:")
            lines.extend([f"- {x}" for x in described_components])
        return "\n".join(lines)

    @staticmethod
    def _extract_dimension_value(short_description: str, dimension_name: str) -> str:
        if not short_description:
            return ''
        if dimension_name == 'length':
            m = re.search(r'длина\s*\(мм\)\s*([0-9]+(?:[,.][0-9]+)?)', short_description, flags=re.IGNORECASE)
            if m:
                return f"{m.group(1)} мм"
        if dimension_name == 'dimension':
            m = re.search(r'(?:диаметр|размер|наружный диаметр|внутренний диаметр)\s*\([^)]*\)\s*([0-9хx/,.]+)', short_description, flags=re.IGNORECASE)
            if m:
                return m.group(1)
        return ''

    @classmethod
    def _format_dimension_answer(cls, sku: SkuRecord, dimension_name: str) -> str:
        value = cls._extract_dimension_value(sku.short_description, dimension_name)
        if dimension_name == 'length' and value:
            return f"У артикула {sku.article} длина: {value}. Характеристики: {sku.short_description}."
        if value:
            return f"У артикула {sku.article} размер/диаметр: {value}. Характеристики: {sku.short_description}."
        return cls._format_sku_answer(sku)

    @staticmethod
    def _format_pipe_compatibility_answer(query: str, rag_results: list) -> str:
        q = query.lower()
        if not any(x in q for x in [
            'встанет', 'влезет', 'подойд', 'подходит', 'совместим',
            'плотно', 'сидеть', 'сядет', 'под трубу', 'под трубку', 'трубка',
            'для какой трубы', 'стенк', 'толщина стенки', 'под какую толщину', 'подойдут гильзы',
            'имеет значение',
        ]):
            return ''

        context = '\n'.join(str(r.text) for r in rag_results[:5])
        if not context:
            return ''

        title_has_16_angle = bool(re.search(r'уголок[^\n]{0,80}16\s*[xх]\s*16', q))
        supports_16_22 = re.search(r'16\s*мм[^\n.]+2[,.]2\s*мм', context, flags=re.IGNORECASE)
        supports_20_28 = re.search(r'20\s*мм[^\n.]+2[,.]8\s*мм', context, flags=re.IGNORECASE)
        asks_16_20 = (
            re.search(r'16\s*[xх/]\s*2(?:[,.]0)?(?![,.]\d)', q)
            or ('16' in q and re.search(r'2[,.]0', q))
            or ('16' in q and re.search(r'стенк[^\n?.]{0,20}\b2\b', q))
        )
        asks_16_22 = re.search(r'16\s*[xх/]\s*2[,.]2', q) or ('16' in q and re.search(r'2[,.]2', q))
        asks_16_26 = re.search(r'16\s*[xх/]\s*2[,.]6', q)
        asks_20_28 = re.search(r'20\s*[xх/\-]\s*2[,.]8', q)
        asks_inner_157 = 'внутрен' in q and re.search(r'15[,.]7', q)
        asks_inner_diameter = 'внутрен' in q and 'диаметр' in q
        asks_hose_inner = ('шланг' in q or 'дренаж' in q) and 'внутрен' in q

        if title_has_16_angle and asks_20_28 and supports_20_28:
            return (
                "Уголок 16x16 для трубы 20x2,8 не подойдет: это другой размер. "
                "Нужен размер 20: по базе знаний геометрия 20x2,8 мм поддерживается аксиальными фитингами ONDO размера 20, "
                "например уголком 20x20. Совместимость с конкретной трубой STOUT по бренду в базе не указана."
            )

        if asks_inner_157 and supports_16_22:
            return (
                "По базе знаний аксиальные фитинги ONDO рассчитаны на полимерную трубу "
                "с наружным диаметром 16 мм и толщиной стенки 2,2 мм. По внутреннему диаметру "
                "трубки 15,7 мм совместимость подтвердить нельзя: для аксиального соединения важны "
                "наружный диаметр и толщина стенки трубы. Для дренажной трубки кондиционера с внутренним "
                "диаметром 15,7 мм в базе нет подтверждения, что она будет плотно сидеть на таком тройнике."
            )
        if asks_hose_inner and supports_16_22:
            return (
                "Для шланга с внутренним диаметром 16 мм совместимость подтвердить нельзя. "
                "В базе знаний аксиальные фитинги ONDO подбираются для PEX-труб по наружному диаметру "
                "и толщине стенки: 16x2,2 мм или 20x2,8 мм, а не по внутреннему диаметру шланга."
            )
        if asks_inner_diameter and supports_16_22:
            return (
                "В базе знаний совместимость для аксиальных фитингов ONDO указана не по внутреннему диаметру, "
                "а по наружному диаметру и толщине стенки трубы: для размера 16 — труба 16x2,2 мм. "
                "Подбор по внутреннему диаметру в базе не подтвержден."
            )

        if asks_16_20 and asks_16_22 and supports_16_22:
            return (
                "Из этих вариантов по базе знаний подтверждена труба 16x2,2 мм. "
                "Для трубы 16x2,0 мм подтверждения в базе нет."
            )
        if asks_16_20 and supports_16_22:
            return (
                "По базе знаний для аксиальных фитингов ONDO указана совместимость с трубой 16x2,2 мм "
                "(наружный диаметр 16 мм, толщина стенки 2,2 мм). "
                "Для трубы 16x2,0 "
                "подтверждения в базе нет, поэтому я бы не подтверждал совместимость без документа производителя."
            )
        if asks_16_22 and asks_16_26 and supports_16_22:
            return (
                "Из этих вариантов по базе знаний подтверждена труба 16x2,2 мм. "
                "Для трубы 16x2,6 мм подтверждения в базе нет."
            )
        if asks_16_22 and supports_16_22:
            return "Да, в базе знаний указана совместимость с трубой 16x2,2 мм для аксиальных фитингов ONDO."
        if asks_16_26 and supports_16_22:
            return "Для трубы 16x2,6 мм подтверждения в базе нет. В базе указана труба 16x2,2 мм."
        if asks_20_28 and supports_20_28:
            return (
                "По геометрии в базе знаний указана совместимость с трубой 20x2,8 мм для аксиальных фитингов ONDO. "
                "Совместимость с конкретным брендом трубы в базе не указана, поэтому дополнительно проверьте материал PEX и размер фитинга 20."
            )
        return ''

    @staticmethod
    def _format_known_or_missing_spec_answer(query: str, rag_results: list) -> str:
        q = query.lower()
        context = '\n'.join(str(r.text) for r in rag_results[:5])
        if not context:
            return ''
        supports_16_22 = re.search(r'16\s*мм[^\n.]+2[,.]2\s*мм', context, flags=re.IGNORECASE)

        if 'производител' in q or 'кто производит' in q:
            for chunk in rag_results[:5]:
                manufacturer = str(getattr(chunk, 'metadata', {}).get('manufacturer', '')).strip()
                country = str(getattr(chunk, 'metadata', {}).get('country', '')).strip()
                if manufacturer:
                    suffix = f", {country}" if country else ""
                    return f"Производитель: {manufacturer}{suffix}."
            m = re.search(r'Manufacturer:\s*([^\n]+)', context, flags=re.IGNORECASE)
            if not m:
                m = re.search(r'MANUFACTURER\s*\n?-?\s*([^\n]+)', context, flags=re.IGNORECASE)
            if m:
                return f"Производитель: {m.group(1).strip()}."
            if 'Sabie S.r.l.' in context:
                return "Производитель: Sabie S.r.l., Италия."

        if 'вес' in q:
            return "В базе знаний для аксиальных фитингов ONDO вес одной штуки не указан."

        if 'шаг резьб' in q:
            if 'Тип резьбы: трубная' in context:
                return "В базе знаний указан тип резьбы: трубная. Точный шаг резьбы в базе не указан."
            return "Точный шаг резьбы в базе знаний не указан."

        if 'марка' in q and 'латун' in q:
            if 'горячештампованная латунь' in context.lower():
                return "В базе знаний указан материал корпуса: горячештампованная латунь. Конкретная марка латуни и метод контроля в базе не указаны."
            return "Конкретная марка латуни и метод контроля в базе знаний не указаны."

        if 'проходн' in q and 'диаметр' in q:
            if 'не заужает внутренний диаметр' in context.lower():
                return "В базе знаний сказано, что конструкция соединения не заужает внутренний диаметр трубопровода. Точное значение проходного диаметра в мм не указано."
            return "Точное значение внутреннего проходного диаметра в базе знаний не указано."

        if 'посадочн' in q:
            return "Длина посадочного места в базе знаний не указана."

        if 'давлен' in q:
            if '1.6 МПа' in context or '1,6 МПа' in context:
                if 'горяч' in q or 'вод' in q:
                    return (
                        "Рабочее давление для аксиальных фитингов ONDO: 1,6 МПа, это примерно 16 бар. "
                        "Для горячей воды в базе указан диапазон температуры рабочей среды +5…+95 °C."
                    )
                return "Номинальное давление аксиальных фитингов ONDO: 1,6 МПа. Это примерно 16 бар."

        if ('инструмент' in q or 'руками' in q) and ('монтаж' in q or 'монтир' in q or 'зафиксировать' in q):
            return "Монтаж аксиальных фитингов выполняется специальным инструментом: ручным или электрическим/аккумуляторным. Фиксировать руками по базе знаний не предусмотрено."

        if 'длин' in q and 'гильз' in q:
            m = re.search(r'OXS00016\s*-\s*([^\n]+длина\s*\(мм\)\s*24[^\n]*)', context, flags=re.IGNORECASE)
            if m:
                return f"Гильза аксиальная 16: длина 24 мм. Характеристики: {m.group(1).strip()}."
            return "Гильза аксиальная 16: в базе знаний указана длина 24 мм."

        if ('накидн' in q or 'накладн' in q or 'накидной гайк' in q) and ('16' in q or '1/2' in q or '3/4' in q):
            return (
                "В базе знаний у ONDO указаны аксиальные фитинги с накидной гайкой, но детальное описание по ним неполное. "
                "Похожие артикулы из списка: OXCA1612 для 16x1/2 и OXCA1634 для 16x3/4. "
                "Перед отправкой ссылки лучше проверить карточку товара по этим артикулам."
            )

        if ('14мм' in q or '14 мм' in q or re.search(r'\b14\s*мм\b', q)) and ('угол' in q or 'тройник' in q):
            return "В базе знаний по аксиальным фитингам ONDO есть размеры 16 и 20 мм. Уголки и тройники на 14 мм в базе не указаны."

        if ('в продаже' in q or 'в наличии' in q or 'есть ли' in q) and 'угол' in q and '16' in q:
            return (
                "По базе знаний для уголка аксиального ONDO размера 16 указан артикул OXL01616. "
                "Если нужен уголок 16x1/2 с резьбой, есть OXLF1612 с внутренней резьбой и OXLM1612 с наружной резьбой. "
                "Актуальное наличие нужно проверять в каталоге/на маркетплейсе."
            )

        if ('бывают' in q or 'есть' in q or 'под какую толщину' in q or 'толщину' in q) and 'гильз' in q and '16' in q:
            if re.search(r'2[,.]0|\b2\b', q) and supports_16_22:
                return (
                    "В базе знаний для аксиальных фитингов ONDO размера 16 указана труба 16x2,2 мм. "
                    "Гильзы для трубы 16x2,0 мм в базе не указаны; артикул OXS00016 относится к размеру 16 под указанную геометрию 16x2,2."
                )

        if ('рехау' in q or 'rehau' in q or 'stabil' in q) and '16' in q:
            if re.search(r'2[,.]6', q):
                return (
                    "Для REHAU Stabil 16,2x2,6 совместимость по базе знаний не подтверждена. "
                    "Для аксиальных фитингов ONDO размера 16 указана труба 16x2,2 мм."
                )
            return (
                "Совместимость с брендом REHAU в базе знаний отдельно не указана. "
                "Для ONDO подтверждена геометрия трубы 16x2,2 мм; если труба REHAU отличается по размеру, совместимость не подтверждаю."
            )

        return ''

    @staticmethod
    def _matches_item_type(target_type: str, article_type: str) -> bool:
        target = str(target_type or '').strip().lower()
        article = str(article_type or '').strip().lower()
        if not target or not article:
            return False
        if target in article:
            return True

        stems = {
            'гильза': 'гильз',
            'муфта': 'муфт',
            'тройник': 'тройник',
            'уголок': 'угол',
            'соединение': 'соединен',
            'кран': 'кран',
            'коллектор': 'коллектор',
        }
        stem = stems.get(target, target)
        return stem in article

    async def answer(
        self,
        query: str,
        session_id: str | None = None,
        answer_style: str = 'detailed',
        conversation_id: str | None = None,
    ) -> dict:
        if not getattr(self, 'reasoner', None):
            self.reasoner = ProductReasoner(self.sku)
        started = now_ms()
        request_id = gen_request_id()
        sid = self.memory.ensure_session(session_id)
        cid = self.memory.ensure_conversation(sid, conversation_id)
        state = self.memory.get_state(cid, session_id=sid)
        recent = self.memory.get_recent_messages(cid, limit=settings.CHAT_HISTORY_LIMIT, session_id=sid)
        resolved_query = query.strip()
        expanded_query = self.expander.expand(resolved_query)
        slots = extract_slots(resolved_query)

        self.memory.append_message(sid, cid, role='user', content=query, request_id=request_id, metadata_json={'resolved_query': resolved_query})
        article = extract_article_candidate(resolved_query)
        normalized_sku = normalize_sku(article)
        requested_article = normalized_sku.normalized or None
        intent = self._infer_intent(resolved_query, requested_article)
        router = {
            'intent': intent,
            'selected_route': 'minimal_rag_pipeline',
            'expected_answer_type': 'consultant_answer',
            'confidence': 0.9 if requested_article else 0.7,
            'reason': 'minimal_pipeline',
            'tools': [],
        }
        tools_called: list[str] = []
        empty_results: list[str] = []
        fallback_used = False

        if intent == 'clarify':
            answer = 'Не совсем понял запрос. Уточните, пожалуйста, товар, артикул или параметр (например: "артикулы гильз ONDO" или "паспорт на ONDO...").'
            payload = {
                'session_id': sid, 'conversation_id': cid, 'request_id': request_id, 'answer': answer,
                'original_query': query, 'resolved_query': resolved_query, 'depends_on_history': False,
                'answer_mode': 'clarify', 'sources': [], 'documents': [], 'used_web_search': False,
                'web_results': [], 'confidence': 'low', 'tools_used': ['clarify'],
                'retrieval_trace': [],
                'route': router,
            }
            self.memory.append_message(sid, cid, role='assistant', content=answer, request_id=request_id, metadata_json={'intent': 'ambiguous_question', 'answer_mode': 'clarify'})
            return payload

        if intent == 'smalltalk':
            answer = self._smalltalk_answer(query)
            payload = {
                'session_id': sid, 'conversation_id': cid, 'request_id': request_id, 'answer': answer,
                'original_query': query, 'resolved_query': resolved_query, 'depends_on_history': False,
                'answer_mode': 'short_answer', 'sources': [], 'documents': [], 'used_web_search': False,
                'web_results': [], 'confidence': 'high', 'tools_used': ['smalltalk'],
                'retrieval_trace': [],
                'route': router,
            }
            self.memory.append_message(sid, cid, role='assistant', content=answer, request_id=request_id, metadata_json={'intent': intent, 'answer_mode': 'short_answer'})
            return payload

        if intent == 'out_of_scope':
            answer = 'Я консультирую только по сантехническим товарам и связанной документации.'
            payload = {
                'session_id': sid, 'conversation_id': cid, 'request_id': request_id, 'answer': answer,
                'original_query': query, 'resolved_query': resolved_query, 'depends_on_history': False,
                'answer_mode': 'not_enough_data', 'sources': [], 'documents': [], 'used_web_search': False,
                'web_results': [], 'confidence': 'high', 'tools_used': ['refuse'],
                'retrieval_trace': [],
                'route': router,
            }
            self.memory.append_message(sid, cid, role='assistant', content=answer, request_id=request_id, metadata_json={'intent': intent})
            return payload

        sku_result = None
        base_sku_result = None
        kit_from_global = None
        if requested_article:
            tools_called.append('sku_lookup')
            sku_result = self.sku.lookup(requested_article)
            if normalized_sku.base_article and normalized_sku.base_article != requested_article:
                base_sku_result = self.sku.lookup(normalized_sku.base_article)
            if not sku_result:
                empty_results.append('sku_lookup')
        matched_sku = sku_result or base_sku_result
        if requested_article:
            tools_called.append('kit_lookup')
            kit_from_global = self.kits.lookup(requested_article) or self.kits.lookup(normalized_sku.base_article)
            if not kit_from_global:
                empty_results.append('kit_lookup')

        rag_results: list[RetrievedChunk] = []
        chroma_unavailable = not self.rag.available
        tools_called.append('rag_search')
        rag_results = self._collect_relevant_context(
            query=expanded_query,
            requested_article=requested_article,
            sku_result=sku_result,
            base_sku_result=base_sku_result,
        )
        if not rag_results:
            empty_results.append('rag_search')
        rag_results_strong = filter_relevant_chunks(rag_results)

        ql = resolved_query.lower()
        doc_type = self._extract_doc_type(resolved_query, slots.requested_doc_type)

        doc_results = []
        if intent == 'document_request' or requested_article:
            tools_called.append('document_search')
            doc_results = self.docs.search(expanded_query, article=requested_article or normalized_sku.base_article, doc_type=doc_type)
            if not doc_results:
                empty_results.append('document_search')

        web_results = []
        used_web_search = False
        local_miss = not matched_sku and not doc_results and not has_strong_rag_context(rag_results)
        should_web_search = settings.ENABLE_WEB_SEARCH and local_miss
        if should_web_search:
            tools_called.append('san_team_search')
            web_response = self.web.search(resolved_query)
            web_results = await web_response if inspect.isawaitable(web_response) else web_response
            used_web_search = bool(web_results)
            if not web_results:
                empty_results.append('san_team_search')

        conf = compute_confidence(
            bool(matched_sku or kit_from_global),
            [r.score for r in rag_results_strong or rag_results],
            bool(doc_results),
            used_web_only=used_web_search and not rag_results_strong,
        )

        answer_mode = 'short_answer'
        if intent in {'installation_or_usage_question', 'installation_question', 'warranty_question'}:
            answer_mode = 'technical_answer'
        if intent in {'compatibility_question', 'related_product_question', 'assortment_question', 'technical_spec_question'}:
            answer_mode = 'technical_answer'
        if intent == 'document_request':
            answer_mode = 'document_answer'
        if intent in {'product_question', 'price_or_availability_question'} or ('подоб' in ql and intent != 'knowledge_base_question'):
            answer_mode = 'selection_answer'

        display_rag = rag_results_strong or rag_results
        sources = [{
            'doc_id': r.metadata.get('doc_id', ''),
            'product': r.metadata.get('product', ''),
            'brand': r.metadata.get('brand', ''),
            'category': r.metadata.get('category', ''),
            'section': r.metadata.get('section', ''),
            'source_file': r.metadata.get('source_file', ''),
            'score': r.score,
        } for r in display_rag[:5]]
        documents = [{'title': d['title'], 'type': d['type'], 'product': d['product'], 'brand': d['brand'], 'public_url': d['public_url']} for d in doc_results]
        product_evidence = self.reasoner.build_evidence(
            original_query=query,
            resolved_query=resolved_query,
            intent=intent,
            slots=slots,
            requested_article=requested_article,
            sku_result=sku_result,
            base_sku_result=base_sku_result,
            kit_result=kit_from_global,
            rag_results=display_rag,
            documents=documents,
        )

        answer = ''
        final_answer_source = 'llm_composed'
        deterministic_reason = ''
        rag_usable = has_strong_rag_context(rag_results) or (
            intent in KB_SYNTHESIS_INTENTS and has_weak_rag_context(rag_results)
        )
        has_evidence = bool(matched_sku or kit_from_global or documents or rag_usable or web_results or product_evidence.decision or product_evidence.answer_hints)

        try:
            rag_for_prompt = chunks_for_llm(rag_results, intent, slots)
            tools_called.append('llm')
            prompt = build_user_prompt({
                'original_query': query,
                'resolved_query': resolved_query,
                'conversation_state': {},
                'recent_messages': [],
                'router_decision': router,
                'sku_result': matched_sku.model_dump() if matched_sku else None,
                'product_evidence': product_evidence.model_dump(),
                'product_cards': [],
                'rag_chunks': [self._sanitize_context(r.text) for r in rag_for_prompt[:5]],
                'document_results': documents,
                'web_results': web_results,
                'confidence': conf,
                'answer_mode': answer_mode,
                'answer_style': answer_style,
            })
            self._log_prompt_preview(request_id, SYSTEM_PROMPT, prompt)
            answer = await self.llm.chat(SYSTEM_PROMPT, prompt)
            answer_warnings = self.reasoner.validate_answer_against_context(answer, product_evidence)
            if answer_warnings:
                product_evidence.warnings.extend(answer_warnings)
            final_answer_source = 'llm_composed'
        except Exception:
            fallback_used = True
            composed = self.reasoner.compose_deterministic_answer(product_evidence, sku_result=matched_sku)
            if composed:
                answer = composed
                final_answer_source = 'evidence_fallback'
            elif intent == 'document_request' and documents:
                answer = 'Найдены документы: ' + '; '.join([f"{d['title']} ({d['public_url']})" for d in documents[:5]])
                final_answer_source = 'document_fallback'
            elif matched_sku:
                answer = f"Артикул {matched_sku.article}: {matched_sku.product}, бренд {matched_sku.brand}, категория {matched_sku.category}."
                final_answer_source = 'sku_fallback'
            elif has_evidence:
                answer = 'Не подтверждено. В найденном контексте недостаточно прямых данных для уверенного ответа.'
                final_answer_source = 'evidence_soft_fallback'
            else:
                answer = build_no_context_fallback(intent)
                final_answer_source = 'fallback'
                tools_called.append('fallback')

        if answer_style == 'short' and answer:
            parts = re.split(r'(?<=[.!?])\s+', answer.strip())
            answer = ' '.join(parts[:6])

        if chroma_unavailable:
            answer += '\n\nСемантический поиск временно недоступен, использованы точные индексы.'
        if used_web_search and web_results and 'san.team' not in answer:
            answer += '\n\nЧасть информации найдена через поиск по сайту san.team.'

        if conf['label'] == 'low' or (not sources and not documents and not matched_sku and not kit_from_global):
            save_knowledge_gap(
                request_id=request_id,
                original_query=query,
                resolved_query=resolved_query,
                intent=intent,
                tools_used=tools_called,
                reason=conf.get('reason', 'low_confidence_or_no_results'),
            )

        versions = get_current_index_versions()
        latency = now_ms() - started
        retrieval_trace = self._build_retrieval_trace(
            query=resolved_query,
            article=requested_article,
            sku_result=matched_sku,
            kit_from_global=kit_from_global,
            rag_results=display_rag,
            documents=documents,
            web_results=web_results,
            tools_called=tools_called,
            empty_results=empty_results,
            slots=slots,
            intent=intent,
            product_evidence=product_evidence.model_dump(),
            final_answer_source=final_answer_source,
            deterministic_reason=deterministic_reason or product_evidence.deterministic_reason,
        )
        response = {
            'session_id': sid,
            'conversation_id': cid,
            'request_id': request_id,
            'answer': answer,
            'original_query': query,
            'resolved_query': resolved_query,
            'depends_on_history': False,
            'answer_mode': answer_mode,
            'sources': sources,
            'documents': documents,
            'used_web_search': used_web_search,
            'web_results': web_results,
            'confidence': conf['label'],
            'tools_used': tools_called,
            'retrieval_trace': retrieval_trace,
            'route': router,
        }

        save_chat_request(
            request_id=request_id,
            session_id=sid,
            conversation_id=cid,
            user_message=query,
            answer=answer,
            intent=intent,
            answer_mode=answer_mode,
            router_mode=settings.ROUTER_MODE,
            tools_used_json=tools_called,
            sources_json=sources,
            documents_json=documents,
            used_web_search=used_web_search,
            confidence=conf['label'],
            model_name=settings.LLM_MODEL,
            latency_ms=latency,
            rag_index_version=versions.get('rag_index_version'),
            documents_index_version=versions.get('documents_index_version'),
            needs_human_review=(conf['label'] == 'low'),
        )

        current_product = matched_sku.product if matched_sku else (sources[0]['product'] if sources else None)
        current_brand = matched_sku.brand if matched_sku else (sources[0]['brand'] if sources else None)
        current_category = matched_sku.category if matched_sku else (sources[0]['category'] if sources else None)
        current_article = matched_sku.article if matched_sku else requested_article
        current_doc_id = sources[0]['doc_id'] if sources else state.get('current_doc_id')

        self.memory.update_state(
            cid,
            sid,
            current_product=current_product,
            current_brand=current_brand,
            current_article=current_article,
            current_category=current_category,
            current_doc_id=current_doc_id,
            last_intent=intent,
            last_answer_mode=answer_mode,
            last_sources_json=sources,
            last_documents_json=documents,
        )
        self.memory.append_message(sid, cid, role='assistant', content=answer, request_id=request_id, metadata_json={'intent': intent, 'answer_mode': answer_mode})

        if settings.ENABLE_ANSWER_EVALUATION:
            await evaluate_answer({'query': resolved_query, 'answer': answer, 'sources': sources})

        return response

    @staticmethod
    def _build_retrieval_trace(
        query: str,
        article: str | None,
        sku_result: SkuRecord | None,
        kit_from_global: KitRecord | None,
        rag_results: list,
        documents: list[dict],
        web_results: list,
        tools_called: list[str],
        empty_results: list[str],
        slots,
        intent: str,
        product_evidence: dict,
        final_answer_source: str,
        deterministic_reason: str | None,
    ) -> list[dict]:
        trace: list[dict] = []

        if 'sku_lookup' in tools_called:
            if sku_result:
                trace.append(build_tool_payload(
                    query=article or query,
                    results=[sku_result.model_dump()],
                    meta={'tool': 'sku_lookup'},
                    mode='exact_article',
                ))
            else:
                trace.append(empty_results_payload(
                    query=article or query,
                    note='Exact article was not found in SKU index.',
                    meta={'tool': 'sku_lookup'},
                    mode='exact_article',
                ))

        if 'kit_lookup' in tools_called:
            if kit_from_global:
                trace.append(build_tool_payload(
                    query=article or query,
                    results=[kit_from_global.model_dump()],
                    meta={'tool': 'kit_lookup'},
                    mode='exact_kit_article',
                ))
            else:
                trace.append(empty_results_payload(
                    query=article or query,
                    note='Exact kit article was not found in kit index.',
                    meta={'tool': 'kit_lookup'},
                    mode='exact_kit_article',
                ))

        if 'rag_search' in tools_called:
            rag_payloads = []
            for chunk in rag_results[:5]:
                metadata = getattr(chunk, 'metadata', {}) or {}
                rag_payloads.append({
                    'doc_id': metadata.get('doc_id', ''),
                    'product': metadata.get('product', ''),
                    'section_group': metadata.get('section_group', ''),
                    'section': metadata.get('section', ''),
                    'source_file': metadata.get('source_file', ''),
                    'score': getattr(chunk, 'score', 0),
                })
            if rag_payloads:
                trace.append(build_tool_payload(
                    query=query,
                    results=rag_payloads,
                    meta={'tool': 'rag_search'},
                    mode='section_aware_chunks',
                ))
            else:
                trace.append(empty_results_payload(
                    query=query,
                    note='No RAG chunks passed retrieval filters.',
                    meta={'tool': 'rag_search'},
                    mode='section_aware_chunks',
                ))

        if 'document_search' in tools_called:
            if documents:
                trace.append(build_tool_payload(
                    query=query,
                    results=documents,
                    meta={'tool': 'document_search'},
                    mode='document_index',
                ))
            else:
                trace.append(empty_results_payload(
                    query=query,
                    note='No matching documents found.',
                    meta={'tool': 'document_search'},
                    mode='document_index',
                ))

        if 'san_team_search' in tools_called:
            if web_results:
                trace.append(build_tool_payload(
                    query=query,
                    results=web_results,
                    meta={'tool': 'san_team_search'},
                    mode='site_search',
                ))
            else:
                trace.append(empty_results_payload(
                    query=query,
                    note='Site search returned no results.',
                    meta={'tool': 'san_team_search'},
                    mode='site_search',
                ))

        if 'fallback' in tools_called:
            trace.append(empty_results_payload(
                query=query,
                note='No reliable local context was found; fallback answer was used.',
                meta={'tool': 'fallback', 'empty_tools': empty_results},
                mode='no_context',
            ))

        if 'llm' in tools_called:
            trace.append(build_tool_payload(
                query=query,
                results=[{
                    'used_rag_chunks': len(rag_results[:5]),
                    'used_documents': len(documents[:5]),
                    'used_web_results': len(web_results[:5]),
                }],
                meta={'tool': 'llm_composer', 'final_answer_source': final_answer_source},
                mode='composer',
            ))

        trace.append(build_tool_payload(
            query=query,
            results=[{
                'intent': intent,
                'article': article or '',
                'product_type': slots.item_type,
                'requested_size': getattr(slots, 'requested_size', ''),
                'requested_pipe_size': getattr(slots, 'requested_pipe_size', ''),
                'decision': product_evidence.get('decision', ''),
                'decision_reason': product_evidence.get('decision_reason', ''),
                'recommended_articles': product_evidence.get('recommended_articles', []),
            }],
            meta={
                'tool': 'product_reasoner',
                'final_answer_source': final_answer_source,
                'deterministic_reason': deterministic_reason or '',
            },
            mode='evidence',
        ))

        return trace
