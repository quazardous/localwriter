# Portage mcp-libre → localwriter

Référence: [tool_comparison_report.md](tool_comparison_report.md)

---

## Cross-cutting: améliorer les tools existants

### Locator support sur les tools core writer
- [ ] `read_paragraphs` — ajouter param `locator` (bookmark/page/section/heading_text)
- [ ] `insert_at_paragraph` — ajouter params `locator`, `style`
- [ ] `add_comment` — ajouter params `locator`, `paragraph_index` (en plus de `search_text`)
- [ ] `delete_comment` — ajouter param `author` (bulk delete par auteur)
- [ ] `list_comments` — ajouter param `author_filter`

### search_fulltext — params manquants
- [ ] Ajouter `around_page`, `page_radius`, `include_pages` (filtrage par proximité de page)

### execute_batch — params manquants
- [ ] Ajouter `check_conditions` (vérifie stop signals entre opérations)
- [ ] Ajouter `revision_comment` (global + per-operation)

### get_document_info — compléter les props
- [ ] Ajouter `keywords`, `creation_date`, `modification_date` (actuellement manquants vs get_document_properties)

---

## Writer Content / Editing — tools manquants

- [ ] `set_paragraph_text` — remplace le texte d'un paragraphe (préserve le style), retourne paragraph_index + bookmark
- [ ] `set_paragraph_style` — change le style d'un paragraphe par locator
- [ ] `delete_paragraph` — supprime un paragraphe par locator
- [ ] `duplicate_paragraph` — duplique un paragraphe (avec style), param `count` pour blocs
- [ ] `clone_heading_block` — clone un bloc heading complet (heading + sous-headings + body)
- [ ] `insert_paragraphs_batch` — insertion de multiples paragraphes en une transaction UNO

---

## Writer Search — tools manquants

- [ ] `search_in_document` — recherche LO native avec contexte paragraphe (regex, case_sensitive, context_paragraphs)
- [ ] `replace_in_document` — find-and-replace dédié avec support regex, préserve le formatage

---

## Writer Tables — tool manquant

- [ ] `create_table` — créer une table à une position paragraphe avec support locator

---

## Writer Structural — tools manquants

- [ ] `read_section` — lire le contenu d'une section nommée
- [ ] `resolve_bookmark` — résoudre un bookmark vers son paragraph_index + heading text
- [ ] `update_fields` — rafraîchir tous les champs (dates, numéros de page, renvois)

---

## Writer Comments / Workflow — tools manquants

- [ ] `resolve_comment` — résoudre un commentaire avec message de résolution
- [ ] `scan_tasks` — scanner les commentaires pour préfixes (TODO-AI, FIX, QUESTION, VALIDATION, NOTE)
- [ ] `get_workflow_status` — lire le dashboard workflow (auteur MCP-WORKFLOW)
- [ ] `set_workflow_status` — créer/mettre à jour le dashboard workflow
- [ ] `check_stop_conditions` — vérifier les signaux stop (commentaires STOP/CANCEL, phase workflow)

---

## Writer Images / Frames — tools manquants (10)

- [ ] `list_images` — lister toutes les images avec nom, dimensions, titre, description
- [ ] `get_image_info` — info détaillée d'une image (URL, dimensions, anchor, orientation, para index)
- [ ] `set_image_properties` — redimensionner, repositionner, recadrer, mettre à jour caption/alt-text
- [ ] `download_image` — télécharger une image URL vers cache local (retry, SSL bypass)
- [ ] `insert_image` — insérer une image depuis fichier/URL avec frame et caption
- [ ] `delete_image` — supprimer une image (et son frame parent optionnellement)
- [ ] `replace_image` — remplacer la source d'une image en gardant frame/position
- [ ] `list_text_frames` — lister tous les text frames
- [ ] `get_text_frame_info` — info détaillée d'un text frame
- [ ] `set_text_frame_properties` — modifier taille, position, wrap, anchor d'un frame

---

## Document Lifecycle — tools manquants

- [ ] `create_document` — créer un nouveau document (writer/calc/impress/draw) avec contenu initial optionnel
- [ ] `open_document` — ouvrir un document par chemin fichier
- [ ] `close_document` — fermer un document par chemin (sans sauvegarder)
- [ ] `list_open_documents` — lister tous les documents ouverts
- [ ] `save_document_as` — sauvegarder/dupliquer sous un nouveau nom
- [ ] `get_recent_documents` — documents récemment ouverts depuis l'historique LO
- [ ] `set_document_properties` — mettre à jour title, author, subject, description, keywords

---

## Impress — tools manquants (3)

- [ ] `list_slides` — lister toutes les slides (nom, layout, titre)
- [ ] `read_slide_text` — lire le texte d'une slide + notes
- [ ] `get_presentation_info` — métadonnées présentation (nombre slides, dimensions, master pages)

---

## Diagnostics / Protection — tools manquants (2)

- [ ] `document_health_check` — diagnostics (headings vides, bookmarks cassés, images orphelines, sauts de niveaux)
- [ ] `set_document_protection` — verrouiller/déverrouiller le document pour édition humaine (UI read-only)

---

## Récapitulatif

| Section | Items |
|---------|-------|
| Cross-cutting (améliorer existants) | 10 |
| Writer Content/Editing | 6 |
| Writer Search | 2 |
| Writer Tables | 1 |
| Writer Structural | 3 |
| Writer Comments/Workflow | 5 |
| Writer Images/Frames | 10 |
| Document Lifecycle | 7 |
| Impress | 3 |
| Diagnostics/Protection | 2 |
| **Total** | **49** |
