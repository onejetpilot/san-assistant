from __future__ import annotations

import re

from app.domain.product_facts import ProductEvidence
from app.indexes.kit_index import KitRecord
from app.indexes.sku_index import SkuIndex, SkuRecord
from app.services.slot_extractor import QuerySlots
from app.rag.retriever import RetrievedChunk


TYPE_STEMS = {
    'гильза': 'гильз',
    'муфта': 'муфт',
    'тройник': 'тройник',
    'уголок': 'угол',
    'соединение': 'соединен',
    'кран': 'кран',
    'коллектор': 'коллектор',
}


class ProductReasoner:
    def __init__(self, sku_index: SkuIndex) -> None:
        self.sku = sku_index

    def build_evidence(
        self,
        *,
        original_query: str,
        resolved_query: str,
        intent: str,
        slots: QuerySlots,
        sku_result: SkuRecord | None,
        kit_result: KitRecord | None,
        rag_results: list[RetrievedChunk],
        documents: list[dict],
    ) -> ProductEvidence:
        evidence = ProductEvidence(
            original_query=original_query,
            resolved_query=resolved_query,
            intent=intent,
            mentioned_articles=[x for x in [sku_result.article if sku_result else None] if x],
            sku_facts=[sku_result.model_dump()] if sku_result else [],
            kit_facts=[kit_result.model_dump()] if kit_result else [],
            component_facts=self._component_facts(sku_result, kit_result),
            rag_facts=[self._summarize_chunk(chunk.text) for chunk in rag_results[:5]],
            document_facts=documents[:5],
            user_requested_product_type=slots.item_type or None,
            user_requested_size=slots.dimension_value or slots.requested_size or None,
            user_requested_pipe_size=slots.requested_pipe_size or None,
            user_requested_dimension=slots.dimension_name or None,
        )
        evidence.answer_hints.extend(self._general_hints(slots, sku_result, rag_results))

        if intent == 'document_request':
            evidence.final_answer_strategy = 'deterministic'
            evidence.deterministic_reason = 'document_request'
            return evidence

        if intent in {'article_lookup', 'kit_composition_question'} and not (
            slots.asks_compatibility or slots.asks_related_product or slots.asks_installation or slots.asks_assortment
        ):
            evidence.final_answer_strategy = 'deterministic'
            evidence.deterministic_reason = 'kit_composition' if intent == 'kit_composition_question' else 'exact_article_lookup'

        if slots.asks_assortment or intent == 'assortment_question':
            self._apply_assortment_rules(evidence, slots, resolved_query)

        if slots.asks_related_product or intent == 'related_product_question':
            self._apply_related_product_rules(evidence, slots, sku_result)

        if slots.asks_compatibility or intent == 'compatibility_question':
            self._apply_compatibility_rules(evidence, slots, resolved_query, sku_result, rag_results)

        if slots.asks_installation or intent == 'installation_or_usage_question':
            self._apply_installation_rules(evidence, rag_results)

        if slots.asks_technical_spec or intent == 'technical_spec_question':
            self._apply_spec_rules(evidence, resolved_query, rag_results, sku_result)

        return evidence

    def compose_deterministic_answer(
        self,
        evidence: ProductEvidence,
        *,
        sku_result: SkuRecord | None,
    ) -> str:
        decision = evidence.decision or ''
        if decision == 'not_compatible':
            extra = f" Подходящий размер: {', '.join(evidence.recommended_articles)}." if evidence.recommended_articles else ''
            return f"Нет, не подойдет. {evidence.decision_reason}.{extra}".strip()
        if decision == 'compatible':
            extra = f" Подходящий артикул: {', '.join(evidence.recommended_articles)}." if evidence.recommended_articles else ''
            return f"Да, подойдет. {evidence.decision_reason}.{extra}".strip()
        if decision == 'not_confirmed':
            return f"Совместимость не подтверждена. {evidence.decision_reason}."
        if decision == 'related_product_found':
            article = ', '.join(evidence.recommended_articles) if evidence.recommended_articles else 'подходящий артикул не найден'
            return f"Нужна гильза {evidence.user_requested_size or ''} мм. Подходящий артикул: {article}.".replace('  ', ' ').strip()
        if decision == 'assortment_missing':
            sizes = ', '.join(evidence.warnings) if evidence.warnings else 'нужный размер'
            return f"В базе этот размер не представлен. В подтвержденном ассортименте указаны размеры {sizes}."
        if decision == 'spec_missing':
            if evidence.decision_reason and 'вес одной штуки' in evidence.decision_reason.lower():
                return 'В базе вес одной штуки не указан.'
            return evidence.decision_reason or 'В базе нет подтвержденных данных по этому параметру.'
        if decision == 'installation_not_confirmed':
            return evidence.decision_reason or 'В базе нет подтверждения по условиям монтажа.'
        if decision == 'installation_confirmed':
            return evidence.decision_reason or 'В базе есть подтверждение по условиям монтажа.'
        if sku_result:
            return f"Артикул {sku_result.article}: {sku_result.product}, бренд {sku_result.brand}, категория {sku_result.category}."
        return ''

    @staticmethod
    def _summarize_chunk(text: str) -> str:
        cleaned = ' '.join(str(text).split())
        return cleaned[:240]

    def _apply_assortment_rules(self, evidence: ProductEvidence, slots: QuerySlots, query: str) -> None:
        q = query.lower()
        requested_size = slots.requested_size or self._extract_mm_size(q)
        types = slots.item_types or ([slots.item_type] if slots.item_type else [])
        available_sizes = self._find_available_sizes(types)
        if requested_size and available_sizes and requested_size not in available_sizes:
            evidence.decision = 'assortment_missing'
            evidence.decision_reason = f"Для категории {', '.join(types) or 'товара'} в базе подтверждены только размеры {', '.join(available_sizes)} мм"
            evidence.warnings = available_sizes
            return
        if requested_size and available_sizes and requested_size in available_sizes:
            evidence.recommended_articles = self._find_articles_by_type_and_size(types[:1], requested_size)[:3]

    def _apply_related_product_rules(self, evidence: ProductEvidence, slots: QuerySlots, sku_result: SkuRecord | None) -> None:
        size = self._extract_sku_size(sku_result) if sku_result else None
        if not size and slots.requested_size:
            size = slots.requested_size
        if not size:
            evidence.missing_facts.append('Не удалось определить размер фитинга для подбора гильзы.')
            return
        evidence.user_requested_size = size
        sleeve = self._find_sleeve_article(size)
        evidence.decision = 'related_product_found'
        evidence.decision_reason = f"Для фитинга размера {size} нужна аксиальная гильза {size} мм"
        if sleeve:
            evidence.recommended_articles = [sleeve]
        else:
            evidence.missing_facts.append(f'Артикул гильзы {size} мм не найден в SKU-индексе.')

    def _apply_compatibility_rules(
        self,
        evidence: ProductEvidence,
        slots: QuerySlots,
        query: str,
        sku_result: SkuRecord | None,
        rag_results: list[RetrievedChunk],
    ) -> None:
        q = query.lower()
        supported = self._supported_pipe_sizes(rag_results)
        sku_size = self._extract_sku_size(sku_result) if sku_result else None
        pipe_size = slots.requested_pipe_size or self._extract_pipe_size(q)
        if pipe_size:
            evidence.user_requested_pipe_size = pipe_size
        if 'внутрен' in q and ('шланг' in q or 'дренаж' in q or 'диаметр' in q):
            evidence.decision = 'not_confirmed'
            evidence.decision_reason = (
                'Аксиальные фитинги подбираются по наружному диаметру и толщине стенки трубы, '
                'а совместимость по внутреннему диаметру шланга в базе не подтверждена'
            )
            if supported:
                evidence.answer_hints.append(
                    f"В базе подтверждены геометрии {', '.join(supported)}."
                )
            return
        if sku_size and pipe_size:
            pipe_outer = pipe_size.split('x', 1)[0]
            if pipe_outer != sku_size:
                evidence.decision = 'not_compatible'
                evidence.decision_reason = f"{sku_result.article} имеет размер {sku_size}, а в вопросе указана труба {pipe_size}"
                evidence.recommended_articles = self._find_similar_articles(sku_result, pipe_outer)
                return
            expected_pipe = next((item for item in supported if item.startswith(f'{sku_size}x')), None)
            if expected_pipe and expected_pipe != pipe_size:
                evidence.decision = 'not_confirmed'
                evidence.decision_reason = f"Для размера {sku_size} в базе подтверждена труба {expected_pipe}, а размер {pipe_size} не подтвержден"
                return
            if expected_pipe == pipe_size:
                evidence.decision = 'compatible'
                evidence.decision_reason = f"Для размера {sku_size} в базе подтверждена труба {pipe_size}"
                if sku_result:
                    evidence.recommended_articles = [sku_result.article]
                return
        if any(brand in q for brand in ['rehau', 'stout', 'рехау', 'стоут']):
            evidence.warnings.append('Совместимость с конкретным брендом трубы в базе отдельно не подтверждена.')
        if supported and not evidence.decision:
            evidence.answer_hints.append(f"В базе подтверждены геометрии {', '.join(supported)}.")

    def _apply_installation_rules(self, evidence: ProductEvidence, rag_results: list[RetrievedChunk]) -> None:
        context = '\n'.join(chunk.text.lower() for chunk in rag_results[:5])
        if not context:
            evidence.decision = 'installation_not_confirmed'
            evidence.decision_reason = 'В базе нет подтвержденного контекста по условиям монтажа.'
            return
        if any(marker in context for marker in ['стяжк', 'скрыт', 'замонол', 'бетон', 'в стену']):
            evidence.decision = 'installation_confirmed'
            evidence.decision_reason = 'В RAG-контексте найдено прямое упоминание условий скрытого монтажа.'
            return
        evidence.decision = 'installation_not_confirmed'
        evidence.decision_reason = 'В найденном RAG-контексте нет прямого подтверждения монтажа в стяжку или скрытым способом.'

    def _apply_spec_rules(
        self,
        evidence: ProductEvidence,
        query: str,
        rag_results: list[RetrievedChunk],
        sku_result: SkuRecord | None,
    ) -> None:
        q = query.lower()
        context = '\n'.join(chunk.text for chunk in rag_results[:5])
        if 'вес' in q:
            if self._extract_weight(context):
                evidence.decision_reason = f"Вес по базе: {self._extract_weight(context)}."
            elif evidence.component_facts:
                evidence.decision = 'spec_missing'
                evidence.decision_reason = 'Вес одной штуки не указан ни у комплекта, ни у базового компонента.'
            else:
                evidence.decision = 'spec_missing'
                evidence.decision_reason = 'Вес одной штуки в базе не указан.'
            return
        if 'длина' in q and sku_result:
            size = self._extract_length(sku_result.short_description)
            if size:
                evidence.decision_reason = f"Длина по SKU: {size}."
                evidence.answer_hints.append(evidence.decision_reason)

    def _general_hints(
        self,
        slots: QuerySlots,
        sku_result: SkuRecord | None,
        rag_results: list[RetrievedChunk],
    ) -> list[str]:
        hints: list[str] = []
        if sku_result:
            hints.append(f"Найден SKU {sku_result.article}: {sku_result.product}.")
        if slots.item_type and slots.requested_size:
            arts = self._find_articles_by_type_and_size([slots.item_type], slots.requested_size)[:3]
            if arts:
                hints.append(f"По индексу есть артикулы: {', '.join(arts)}.")
        component_facts = self._component_facts(sku_result, None)
        if component_facts:
            hints.append('Для комплекта найдены базовые компоненты как source of facts.')
        if rag_results:
            hints.append('Есть RAG-контекст для проверки фактов.')
        return hints

    def _component_facts(self, sku_result: SkuRecord | None, kit_result: KitRecord | None) -> list[dict]:
        components: list[str] = []
        if sku_result and sku_result.kit_components:
            components.extend(sku_result.kit_components)
        if kit_result and kit_result.component_articles:
            components.extend(kit_result.component_articles)
        out: list[dict] = []
        seen: set[str] = set()
        for component in components:
            article = component
            match = re.search(r'([A-Za-zА-Яа-я0-9._\-/]{4,})$', component.strip())
            if match:
                article = match.group(1)
            row = self.sku.lookup(article)
            if not row or row.article in seen:
                continue
            seen.add(row.article)
            out.append(row.model_dump())
        return out

    def _find_available_sizes(self, item_types: list[str]) -> list[str]:
        sizes: list[str] = []
        for row in self.sku.data.values():
            article_type = str(row.get('article_type', '')).lower()
            if item_types and not any(self._matches_item_type(item_type, article_type) for item_type in item_types if item_type):
                continue
            size = self._extract_desc_size(str(row.get('short_description', '')))
            if size and size not in sizes:
                sizes.append(size)
        return sorted(sizes, key=lambda x: int(x))

    def _find_articles_by_type_and_size(self, item_types: list[str], size: str) -> list[str]:
        results: list[str] = []
        for row in self.sku.data.values():
            article_type = str(row.get('article_type', '')).lower()
            if item_types and not any(self._matches_item_type(item_type, article_type) for item_type in item_types if item_type):
                continue
            short = str(row.get('short_description', ''))
            if not re.search(rf'(^|\D){re.escape(size)}(\D|$)', short):
                continue
            article = str(row.get('article', '')).strip()
            if article and article not in results:
                results.append(article)
        return results

    def _find_sleeve_article(self, size: str) -> str | None:
        target = f'OXS000{size}'
        row = self.sku.lookup(target)
        if row:
            return row.article
        for item in self.sku.data.values():
            article = str(item.get('article', '')).strip()
            article_type = str(item.get('article_type', '')).lower()
            if article and self._matches_item_type('гильза', article_type) and re.search(rf'(^|\D){re.escape(size)}(\D|$)', str(item.get('short_description', ''))):
                return article
        return None

    def _find_similar_articles(self, sku_result: SkuRecord, size: str) -> list[str]:
        results: list[str] = []
        for item in self.sku.data.values():
            if str(item.get('brand', '')).upper() != sku_result.brand.upper():
                continue
            article_type = str(item.get('article_type', '')).lower()
            if not self._matches_item_type(sku_result.article_type, article_type) and not self._matches_item_type(article_type, sku_result.article_type):
                continue
            short = str(item.get('short_description', ''))
            if not re.search(rf'(^|\D){re.escape(size)}(\D|$)', short):
                continue
            article = str(item.get('article', '')).strip()
            if article and article != sku_result.article and article not in results:
                results.append(article)
        return results[:3]

    @staticmethod
    def _extract_mm_size(query: str) -> str | None:
        match = re.search(r'\b(14|16|20)\s*мм\b', query)
        return match.group(1) if match else None

    @staticmethod
    def _extract_pipe_size(query: str) -> str | None:
        match = re.search(r'\b(\d{1,2})\s*[xх]\s*(\d(?:[.,]\d)?)\b', query)
        if not match:
            return None
        return f"{match.group(1)}x{match.group(2).replace(',', '.')}"

    @staticmethod
    def _supported_pipe_sizes(rag_results: list[RetrievedChunk]) -> list[str]:
        context = '\n'.join(chunk.text for chunk in rag_results[:5])
        sizes: list[str] = []
        for outer, wall in re.findall(r'(\d{1,2})\s*мм[^\n.]{0,80}?(\d(?:[,.]\d)?)\s*мм', context, flags=re.IGNORECASE):
            normalized = f"{outer}x{wall.replace(',', '.')}"
            if normalized not in sizes:
                sizes.append(normalized)
        return sizes

    @staticmethod
    def _extract_sku_size(sku_result: SkuRecord | None) -> str | None:
        if not sku_result:
            return None
        return ProductReasoner._extract_desc_size(sku_result.short_description)

    @staticmethod
    def _extract_desc_size(description: str) -> str | None:
        if not description:
            return None
        match = re.search(r'(\d{2})\s*[xх]', description, flags=re.IGNORECASE)
        if match:
            return match.group(1)
        match = re.search(r'внутренний диаметр\(мм\)\s*(\d{2})', description, flags=re.IGNORECASE)
        if match:
            return match.group(1)
        match = re.search(r'\b(14|16|20)\b', description)
        return match.group(1) if match else None

    @staticmethod
    def _extract_length(description: str) -> str | None:
        match = re.search(r'длина\(мм\)\s*([0-9]+(?:[,.][0-9]+)?)', description, flags=re.IGNORECASE)
        if not match:
            return None
        return f"{match.group(1)} мм"

    @staticmethod
    def _extract_weight(text: str) -> str | None:
        match = re.search(r'вес[^\n:]*[: ]\s*([0-9]+(?:[,.][0-9]+)?)\s*(кг|г)', text, flags=re.IGNORECASE)
        if not match:
            return None
        return f"{match.group(1)} {match.group(2)}"

    @staticmethod
    def _matches_item_type(target_type: str, article_type: str) -> bool:
        target = str(target_type or '').strip().lower()
        article = str(article_type or '').strip().lower()
        if not target or not article:
            return False
        if target in article or article in target:
            return True
        stem = TYPE_STEMS.get(target, target)
        return stem in article
