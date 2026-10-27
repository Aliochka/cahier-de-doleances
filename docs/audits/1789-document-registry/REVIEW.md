# Vérification documentaire priorisée

**189 notices hautes, 295 intermédiaires, 821 à contrôler par échantillonnage.** File exhaustive machine : `data/review-queue.jsonl`. Ces priorités ne changent aucun statut en validation.

1. Hautes : identités ambiguës ou absentes, erreurs observées, frontières V2 contradictoires, départs internes/composites, ancre commune, portée d’une notice d’absence. Corriger identité et périmètre dans deux décisions séparées. Certaines alertes sont corrélées et ne représentent pas autant d’erreurs indépendantes.
2. Intermédiaires : identités probables et frontières non établies/structurelles. Préserver les pièces associées et documenter la politique d’inclusion des listes, signatures, pouvoirs et annexes.
3. Échantillonnage : propositions fortes simples et contrôles des exclus. Tirer un lot stratifié par tome, longueur et pages partagées. Un bon contrôle de titre ne dispense pas du contrôle des fins.

Ajouter la file distincte de **92 hypothèses V2 sans équivalence d’ancre** et les **55 incertaines V2** ; ne pas additionner mécaniquement les volumes de travail, car certains cas sont déjà inclus dans un dossier ou se recouvrent. Les contrôles nouveaux signalent 15 erreurs de frontières ; ils ne fournissent pas tous des plages complètes corrigées. Un contrôle indépendant devrait prioriser ces erreurs et les anomalies de colonnes.

78 notices possèdent une référence de frontière examinée par Codex, donc 1 227 n’en possèdent pas. Cela ne signifie pas qu’il faille relire ces 1 227 documents intégralement : contrôler les transitions et les exceptions, puis mesurer sur un lot indépendant le risque résiduel. Ne pas convertir automatiquement une règle régulière en certification.

## Liste nominative haute priorité

| Tome | Persée | Document | Motifs |
| --- | --- | --- | --- |
| 1 | [1529](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_1_1_1529) | Cahier du clergé de la sénéchaussée d'Agen | identity_ambigu |
| 1 | [1532](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_1_1_1532) | Cahier du clergé de la sénéchaussée d'Aix | contradiction_or_observed_error, boundary_not_certified |
| 1 | [1533](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_1_1_1533) | Cahier de la noblesse de la sénéchaussée d'Aix | composite_or_internal_start |
| 1 | [1536](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_1_1_1536) | Cahier de la noblesse de la sénéchaussée d'Albret | identity_ambigu, contradiction_or_observed_error, V2_boundary_disagreement, boundary_not_certified |
| 1 | [1537](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_1_1_1537) | Cahier de la noblesse de Nérac (Sénéchaussée d'Albret) | composite_or_internal_start, boundary_not_certified |
| 1 | [1538](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_1_1_1538) | Cahier du tiers-état de la sénéchaussée d'Albret | composite_or_internal_start, boundary_not_certified |
| 1 | [1552](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_1_1_1552) | Cahier du tiers-état du bailliage d'Amont | composite_or_internal_start, boundary_not_certified |
| 1 | [1554](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_1_1_1554) | Cahier de Gray (Bailliage d'Amont ) | composite_or_internal_start, boundary_not_certified |
| 2 | [1563](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_2_1_1563) | Cahier du clergé de la sénéchaussée d'Anjou | V2_boundary_disagreement, composite_or_internal_start |
| 2 | [1564](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_2_1_1564) | Cahier de la noblesse de la sénéchaussée d'Anjou | composite_or_internal_start, boundary_not_certified |
| 2 | [1572](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_2_1_1572) | Cahier du tiers-état de la ville d'Arles | V2_boundary_disagreement, boundary_not_certified |
| 2 | [1573](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_2_1_1573) | Cahiers de quelques corps et communautés de la ville d'Arles | V2_boundary_disagreement, composite_or_internal_start, boundary_not_certified |
| 2 | [1578](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_2_1_1578) | Cahier du clergé de la province d'Artois | contradiction_or_observed_error, boundary_not_certified |
| 2 | [1586](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_2_1_1586) | Cahier du clergé du bailliage d'Auxerre | contradiction_or_observed_error, boundary_not_certified |
| 2 | [1602](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_2_1_1602) | Cahier du baillage secondaire d'Avallon (Bailliage d'Auxois) | contradiction_or_observed_error, boundary_not_certified |
| 2 | [1613](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_2_1_1613) | Cahier des trois ordres du Bassigny-Barrois (Bailliage de Bar-le-Duc ) | identity_non_retrouve, boundary_not_certified |
| 2 | [1615](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_2_1_1615) | Cahier de la noblesse du baillage de Briey (Bailliage de Bar-le-Duc) | composite_or_internal_start, boundary_not_certified |
| 2 | [1620](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_2_1_1620) | Cahier du clergé du baillage de Pont-à-Mousson (Bailliage de Bar-le-Duc) | composite_or_internal_start, boundary_not_certified |
| 2 | [1623](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_2_1_1623) | Cahier de la noblesse du baillage de Saint-Mihiel (Bailliage de Bar-le-Duc) | composite_or_internal_start, boundary_not_certified |
| 2 | [1627](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_2_1_1627) | Cahier du tiers-état du bailliage de Bar-sur-Seine | composite_or_internal_start, boundary_not_certified |
| 2 | [1643](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_2_1_1643) | Cahier de la noblesse de la province du Berry | contradiction_or_observed_error, boundary_not_certified |
| 2 | [1652](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_2_1_1652) | Cahier du tiers-état de la sénéchaussée de Brest | identity_non_retrouve, contradiction_or_observed_error, boundary_not_certified |
| 2 | [1659](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_2_1_1659) | Cahier du commerce de Besançon (Bailliage de Besançon) | composite_or_internal_start, boundary_not_certified |
| 2 | [1671](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_2_1_1671) | Cahier du tiers-état de la sénéchaussée de Bordeaux | V2_boundary_disagreement |
| 2 | [1673](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_2_1_1673) | Cahier des corporations de Bordeaux (Sénéchaussée de Bordeaux) | composite_or_internal_start, boundary_not_certified |
| 2 | [1679](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_2_1_1679) | Cahier de la noblesse du bailliage de Cambrai | identity_ambigu, contradiction_or_observed_error, boundary_not_certified |
| 2 | [1682](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_2_1_1682) | Cahier du clergé de la sénéchaussée de Castelmoron d'Albret | identity_ambigu, contradiction_or_observed_error, boundary_not_certified |
| 2 | [1692](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_2_1_1692) | Cahier du clergé de la sénéchaussée de Châtellerault | identity_ambigu, contradiction_or_observed_error, boundary_not_certified |
| 2 | [1706](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_2_1_1706) | Cahier de la noblesse de la sénéchaussée de Castelnaudary | contradiction_or_observed_error, boundary_not_certified |
| 2 | [1713](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_2_1_1713) | Cahier de la noblesse du bailliage de Châteauneuf en Thimerais | identity_ambigu, boundary_not_certified |
| 2 | [1716](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_2_1_1716) | Cahier de la noblesse du bailliage de Chaumont en Bassigny | identity_non_retrouve, boundary_not_certified |
| 2 | [1717](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_2_1_1717) | Cahier de la noblesse du bailliage de Chaumont en Vexin | contradiction_or_observed_error, absence_scope_must_be_checked, boundary_not_certified |
| 2 | [1724](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_2_1_1724) | Cahier du tiers-état du bailliage de Châteauneuf en Thimerais | identity_ambigu, contradiction_or_observed_error, boundary_not_certified |
| 2 | [1733](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_2_1_1733) | Cahier de la paroisse de Massugas (Sénéchaussée de Castelmoron d'Albret) | identity_non_retrouve, contradiction_or_observed_error, boundary_not_certified |
| 2 | [1738](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_2_1_1738) | Cahier du tiers-état du bailliage de Châlon-sur-Saône | identity_non_retrouve, boundary_not_certified |
| 3 | [1800](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1800) | Cahier du tiers-état du district de Colmar et Schlesladt | identity_non_retrouve, boundary_not_certified |
| 3 | [1801](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1801) | Cahier de la communauté d'Ardiège (Comté de Comminges) | V2_boundary_disagreement, boundary_not_certified |
| 3 | [1802](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1802) | Cahier de la communauté des prébendiers de Lombez (Comté de Comminges) | composite_or_internal_start, boundary_not_certified |
| 3 | [1812](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1812) | Cahier de la paroisse de Saint-Jean-des-Agneaux (Bailliage de Coutances) | identity_non_retrouve, boundary_not_certified |
| 3 | [1829](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1829) | Cahier du tiers-état de la ville de Dijon (Bailliage de Dijon) | identity_ambigu, boundary_not_certified |
| 3 | [1830](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1830) | Cahier du tiers-état du baillage secondaire d'Auxonne (Bailliage de Dijon) | V2_boundary_disagreement, boundary_not_certified |
| 3 | [1887](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1887) | Cahier de la communauté de Landas (Bailliage de Douai) | identity_non_retrouve, boundary_not_certified |
| 3 | [1889](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1889) | Cahier de la communauté de Billon (Bailliage de Douai) | identity_ambigu, boundary_not_certified |
| 3 | [1890](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1890) | Cahier de la communauté de Millonfosse (Bailliage de Douai) | identity_ambigu |
| 3 | [1891](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1891) | Cahier de la communauté de Boussignies (Bailliage de Douai) | contradiction_or_observed_error, boundary_not_certified |
| 3 | [1892](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1892) | Cahier de la communauté de Sin-Lebled (Bailliage de Douai) | composite_or_internal_start, boundary_not_certified |
| 3 | [1895](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1895) | Cahier du village d'Abscon (Bailliage de Douai) | identity_ambigu, boundary_not_certified |
| 3 | [1898](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1898) | Cahier de la communauté d'Alne (Bailliage de Douai) | identity_ambigu |
| 3 | [1915](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1915) | Cahier de la communauté d'Eterpigny (Bailliage de Douai) | identity_ambigu |
| 3 | [1941](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1941) | Cahier du clergé de Digne (Sénéchaussée de Forcalquier) | V2_boundary_disagreement, boundary_not_certified |
| 3 | [1942](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1942) | Cahier du clergé de Riez (Sénéchaussée de Forcalquier) | identity_ambigu, contradiction_or_observed_error, V2_boundary_disagreement, composite_or_internal_start, boundary_not_certified |
| 3 | [1944](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1944) | Cahier du tiers-état de Digne (Sénéchaussée de Forcalquier) | contradiction_or_observed_error, V2_boundary_disagreement, boundary_not_certified |
| 3 | [1945](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1945) | Cahier de la sénéchaussée de Digne (Sénéchaussée de Forcalquier) | composite_or_internal_start, boundary_not_certified |
| 3 | [1946](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1946) | Cahier du clergé de Sisteron (Sénéchaussée de Forcalquier) | V2_boundary_disagreement, composite_or_internal_start, boundary_not_certified |
| 3 | [1947](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1947) | Cahier de la noblesse de Sisteron (Sénéchaussée de Forcalquier) | composite_or_internal_start, boundary_not_certified |
| 3 | [1948](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1948) | Cahier du clergé de Barcelonnette (Sénéchaussée de Forcalquier) | composite_or_internal_start, boundary_not_certified |
| 3 | [1949](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1949) | Cahier du tiers-état de Barcelonnette (Sénéchaussée de Forcalquier) | contradiction_or_observed_error, V2_boundary_disagreement, boundary_not_certified |
| 3 | [1950](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1950) | Cahier de la communauté d'Allos (Sénéchaussée de Forcalquier) | V2_boundary_disagreement, composite_or_internal_start, boundary_not_certified |
| 3 | [1951](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1951) | Cahier de la communauté de Chatelard (Sénéchaussée de Forcalquier) | V2_boundary_disagreement, composite_or_internal_start, boundary_not_certified |
| 3 | [1952](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1952) | Cahier de la communauté de Lauzet (Sénéchaussée de Forcalquier) | identity_non_retrouve, boundary_not_certified |
| 3 | [1953](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1953) | Cahier de la communauté de Revel (Sénéchaussée de Forcalquier) | composite_or_internal_start, boundary_not_certified |
| 3 | [1955](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1955) | Cahier des communautés de Tournoux et Gleisolles (Sénéchaussée de Forcalquier) | V2_boundary_disagreement, composite_or_internal_start, boundary_not_certified |
| 3 | [1956](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1956) | Cahier de la communauté de Fours (Sénéchaussée de Forcalquier) | composite_or_internal_start, boundary_not_certified |
| 3 | [1963](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1963) | Cahier du clergé du bailliage de Gien | composite_or_internal_start, boundary_not_certified |
| 3 | [1971](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1971) | Cahier du tiers-état u Pays de Labourt | absence_scope_must_be_checked, boundary_not_certified |
| 3 | [1976](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1976) | Cahier du tiers-état de la sénéchaussée de La Rochelle | composite_or_internal_start, boundary_not_certified |
| 3 | [1982](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1982) | Cahier de la noblesse de la sénéchaussée de Libourne | composite_or_internal_start, boundary_not_certified |
| 3 | [1992](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1992) | Privilèges de la vicomté de Turenne (Province du Bas-Limousin) | contradiction_or_observed_error |
| 3 | [2000](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_2000) | Cahier du clergé de la sénéchaussée de Limoux | absence_scope_must_be_checked, boundary_not_certified |
| 3 | [2002](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_2002) | Cahier du tiers-état de la sénéchaussée de Limoux | identity_ambigu, boundary_not_certified |
| 3 | [2016](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_2016) | Cahier de la noblesse du bailliage de Mâcon | identity_non_retrouve, boundary_not_certified |
| 3 | [2033](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_2033) | Cahier du tiers-état de la Sénéchaussée de Marseille | composite_or_internal_start |
| 3 | [2039](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_2039) | Cahier de la noblesse du bailliage de Meaux | composite_or_internal_start, boundary_not_certified |
| 3 | [2043](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_2043) | Cahier du tiers-état du bailliage de Melun | V2_boundary_disagreement, boundary_not_certified |
| 3 | [2056](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_2056) | Cahier des vicaires des Trois-Evêchés (Bailliage de Metz) | identity_non_retrouve, boundary_not_certified |
| 3 | [2493](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_2493) | Cahier de la ville de Marseille (Sénéchaussée de Marseille) | composite_or_internal_start, boundary_not_certified |
| 3 | [2943](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_2943) | Cahier de la ville de Barcelonnette (Sénéchaussée de Forcalquier) | composite_or_internal_start, boundary_not_certified |
| 4 | [1745](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_1745) | Cahier de la noblesse du bailliage de Mirecourt | composite_or_internal_start |
| 4 | [1760](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_1760) | Cahier de la noblesse du bailliage d'Orléans | identity_ambigu, boundary_not_certified |
| 4 | [1785](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_1785) | Cahier du tiers-état du bailliage de Nivernais | identity_ambigu, boundary_not_certified |
| 4 | [1788](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_1788) | Cahier de la commune d'Uzent-en-Foix (Sénéchaussée de Pamiers) | identity_ambigu, contradiction_or_observed_error, boundary_not_certified |
| 4 | [1789](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_1789) | Cahier de Vicdessos (Sénéchaussée de Pamiers) | identity_ambigu, contradiction_or_observed_error, boundary_not_certified |
| 4 | [1854](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_1854) | Cahier d'Antony (Paris) | identity_ambigu, boundary_not_certified |
| 4 | [1879](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_1879) | Cahier de Beaubourg (Sainte-Marie-Madeleine de) (Paris) | V2_boundary_disagreement, boundary_not_certified |
| 4 | [1880](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_1880) | Cahier de Beauregard (Paris) | V2_boundary_disagreement, composite_or_internal_start, boundary_not_certified |
| 4 | [1881](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_1881) | Cahier de Belleville (Paris) | composite_or_internal_start, boundary_not_certified |
| 4 | [2073](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2073) | Cahier de Bouffemont (Paris) | identity_ambigu |
| 4 | [2075](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2075) | Cahier de Bouray (Paris) | identity_ambigu |
| 4 | [2105](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2105) | Cahier de Chateauneuf (Paris) | identity_ambigu, boundary_not_certified |
| 4 | [2117](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2117) | Cahier de Chevilly (Paris) | composite_or_internal_start, boundary_not_certified |
| 4 | [2122](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2122) | Cahier de Clamart (Paris) | composite_or_internal_start, boundary_not_certified |
| 4 | [2123](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2123) | Cahier de Claye (Paris) | composite_or_internal_start, boundary_not_certified |
| 4 | [2124](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2124) | Cahier de Clayes (Paris) | identity_ambigu, boundary_not_certified |
| 4 | [2143](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2143) | Cahier de Créteil (Paris) | identity_ambigu, boundary_not_certified |
| 4 | [2156](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2156) | Cahier d'Eragny (Paris) | identity_ambigu, boundary_not_certified |
| 4 | [2167](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2167) | Cahier d'Epinay-les-Saint-Denis | identity_ambigu, contradiction_or_observed_error, boundary_not_certified |
| 4 | [2168](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2168) | Cahier d'Ermont (Paris) | identity_ambigu, contradiction_or_observed_error, boundary_not_certified |
| 4 | [2175](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2175) | Cahier de Ferrières-en-Brie (Paris) | V2_boundary_disagreement, composite_or_internal_start |
| 4 | [2180](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2180) | Cahier de Fontenay-lès-Bagneux (Paris) | identity_ambigu, boundary_not_certified |
| 4 | [2186](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2186) | Cahier de Fourqueux (Paris) | identity_non_retrouve, boundary_not_certified |
| 4 | [2189](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2189) | Cahier de Fresnes (Paris) | identity_ambigu, boundary_not_certified |
| 4 | [2198](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2198) | Cahier de Gif-près-Chevreuse (Paris) | identity_non_retrouve, boundary_not_certified |
| 4 | [2199](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2199) | Cahier de Gometz-le-Châtel (Paris) | composite_or_internal_start, boundary_not_certified |
| 4 | [2201](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2201) | Cahier de Gonesse (Paris) | composite_or_internal_start, boundary_not_certified |
| 4 | [2202](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2202) | Cahier de Gournay-sur-Marne (Paris) | composite_or_internal_start, boundary_not_certified |
| 4 | [2211](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2211) | Cahier de Guiberville (Paris) | composite_or_internal_start, boundary_not_certified |
| 4 | [2212](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2212) | Cahier d'Herbeville (Paris) | composite_or_internal_start, boundary_not_certified |
| 4 | [2213](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2213) | Cahier d'Herblay (Paris) | composite_or_internal_start, boundary_not_certified |
| 4 | [2217](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2217) | Cahier de Jagny-Gonesse (Paris) | identity_ambigu, boundary_not_certified |
| 4 | [2237](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2237) | Cahier de Lessart (Paris) | identity_ambigu, contradiction_or_observed_error, boundary_not_certified |
| 4 | [2238](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2238) | Cahier de Létang-la-Ville (Paris) | identity_ambigu, contradiction_or_observed_error, boundary_not_certified |
| 4 | [2242](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2242) | Cahier de Limours (Paris) | composite_or_internal_start, boundary_not_certified |
| 4 | [2245](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2245) | Cahier de Livry (Paris) | V2_boundary_disagreement, boundary_not_certified |
| 4 | [2264](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2264) | Cahier de Marolles (Paris) | identity_ambigu, contradiction_or_observed_error, boundary_not_certified |
| 4 | [2265](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2265) | Cahier de Marolles-en-Hurepoix (Paris) | identity_ambigu, contradiction_or_observed_error, boundary_not_certified |
| 4 | [2272](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2272) | Cahier de Marielle (Paris) | identity_non_retrouve, boundary_not_certified |
| 4 | [2278](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2278) | Cahier de Messy (Paris) | identity_non_retrouve, boundary_not_certified |
| 4 | [2284](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2284) | Cahier de Monceaux-Villeroy (Paris) | identity_ambigu, boundary_not_certified |
| 4 | [2305](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2305) | Cahier de Nanterre (Paris) | composite_or_internal_start, boundary_not_certified |
| 4 | [2314](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2314) | Cahier de Norville (Paris) | identity_ambigu, contradiction_or_observed_error, boundary_not_certified |
| 4 | [2315](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2315) | Cahier de Nozay (Paris) | identity_ambigu, contradiction_or_observed_error |
| 4 | [2320](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2320) | Cahier d'Ormoy près Lieusaint-en-Brie (Paris) | identity_ambigu, contradiction_or_observed_error, boundary_not_certified |
| 4 | [2321](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2321) | Cahier d'Ormoy-Villabé (Paris) | identity_ambigu, contradiction_or_observed_error, boundary_not_certified |
| 5 | [2340](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2340) | Cahier de messire Carré, propriétaire du fief du Pin (Paris) | identity_ambigu, contradiction_or_observed_error |
| 5 | [2341](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2341) | Cahier du Pin (Paris) | identity_ambigu, contradiction_or_observed_error, boundary_not_certified |
| 5 | [2367](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2367) | Cahier de Rueil (Paris) | identity_ambigu |
| 5 | [2398](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2398) | Cahier de Saint-Prix (Paris) | composite_or_internal_start, boundary_not_certified |
| 5 | [2405](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2405) | Cahier de Santeny (Paris) | V2_boundary_disagreement, boundary_not_certified |
| 5 | [2409](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2409) | Cahier de Savigny-sur-Orge (Paris) | identity_ambigu, boundary_not_certified |
| 5 | [2412](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2412) | Cahier de Sevran (Paris) | identity_ambigu, boundary_not_certified |
| 5 | [2416](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2416) | Cahier de Souilly (Paris) | identity_ambigu, boundary_not_certified |
| 5 | [2422](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2422) | Cahier de Thieux (Paris) | identity_ambigu, boundary_not_certified |
| 5 | [2441](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2441) | Cahier de Vaucresson (Paris) | identity_ambigu, boundary_not_certified |
| 5 | [2446](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2446) | Cahier de Vémart (Paris) | identity_ambigu, boundary_not_certified |
| 5 | [2449](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2449) | Cahier de Vernouillet-sur-Seine (Paris) | identity_ambigu, boundary_not_certified |
| 5 | [2450](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2450) | Cahier de Verrières (Paris) | composite_or_internal_start, boundary_not_certified |
| 5 | [2460](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2460) | Cahier de Ville-du-Bois (Paris) | identity_ambigu, contradiction_or_observed_error, boundary_not_certified |
| 5 | [2461](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2461) | Cahier de Villecresne (Paris) | identity_ambigu, contradiction_or_observed_error |
| 5 | [2477](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2477) | Cahier de Villier-le-Basile (Paris) | identity_ambigu, boundary_not_certified |
| 5 | [2488](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2488) | Cahier de Witz-sous-Montmeillant (Paris) | identity_ambigu, contradiction_or_observed_error, boundary_not_certified |
| 5 | [2489](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2489) | Cahier du clergé (Paris) | identity_ambigu, contradiction_or_observed_error, boundary_not_certified |
| 5 | [2786](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2786) | Cahier du clergé de la paroisse Saint-Paul (Paris intra muros) | identity_ambigu, boundary_not_certified |
| 5 | [2788](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2788) | Cahier de la noblesse du 1er département de Paris intra muros | identity_non_retrouve, boundary_not_certified |
| 5 | [2797](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2797) | Cahier de l'assemblée partielle de l'église de Saint-Germain-des-Prés (Paris intra muros) | identity_non_retrouve, boundary_not_certified |
| 5 | [2799](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2799) | Cahier de l'assemblée partielle de l'église de Saint-Louis de la Culture (Paris intra muros) | identity_ambigu |
| 5 | [2818](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2818) | Cahier du tiers-état de la sénéchaussée de Ploërmel | contradiction_or_observed_error, boundary_not_certified |
| 5 | [2819](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2819) | Délibération de la ville de Pontivy (Sénéchaussée de Ploërmel) | identity_non_retrouve, boundary_not_certified |
| 5 | [2829](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2829) | Cahier de la noblesse de la sénéchaussée de Ponthieu | composite_or_internal_start, boundary_not_certified |
| 5 | [2837](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2837) | Cahier du clergé de la province du Quercy | V2_boundary_disagreement, boundary_not_certified |
| 5 | [2856](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2856) | Cahier du tiers-état de la sénéchaussée de Riom | identity_non_retrouve, boundary_not_certified |
| 5 | [2857](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2857) | Cahier du baillage secondaire de Montaigut (Sénéchaussée de Riom) | contradiction_or_observed_error, boundary_not_certified |
| 5 | [2872](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2872) | Déclaration du clergé de Bretagne (Sénéchaussée de Saint-Brieuc) | identity_non_retrouve, boundary_not_certified |
| 5 | [2873](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2873) | Déclaration de la noblesse de Bretagne (Sénéchaussée de Saint-Brieuc) | identity_non_retrouve, boundary_not_certified |
| 5 | [2877](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2877) | Cahier du tiers-état du bailliage de Saint-Pierre-le-Moutier | V2_boundary_disagreement, boundary_not_certified |
| 5 | [2883](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2883) | Cahier de la noblesse de la sénéchaussée de Saintes | identity_non_retrouve, boundary_not_certified |
| 5 | [2894](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2894) | Cahier du clergé de Bouzonville (Bailliage de Sarreguemines) | composite_or_internal_start, boundary_not_certified |
| 5 | [2914](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2914) | Cahier de la noblesse du bailliage de Sezanne | identity_ambigu, boundary_not_certified |
| 6 | [2520](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2520) | Cahier des magistrats de la ville de Valenciennes | contradiction_or_observed_error, boundary_not_certified |
| 6 | [2521](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2521) | Cahier des habitants de la ville de Valenciennes | identity_ambigu, contradiction_or_observed_error, boundary_not_certified |
| 6 | [2530](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2530) | Cahier de la noblesse du bailliage de Verdun | identity_non_retrouve, boundary_not_certified |
| 6 | [2531](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2531) | Cahier du tiers-état du bailliage de Verdun | absence_scope_must_be_checked, boundary_not_certified |
| 6 | [2537](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2537) | Cahier du clergé de la sénéchaussée de Villefranche-de-Rouergue | absence_scope_must_be_checked, boundary_not_certified |
| 6 | [2557](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2557) | Cahier de la communauté d'Allauch (Sénéchaussée d'Aix) | identity_non_retrouve, boundary_not_certified |
| 6 | [2559](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2559) | Cahier de la communauté d'Ansouis (Sénéchaussée d'Aix) | identity_ambigu, V2_boundary_disagreement, boundary_not_certified |
| 6 | [2562](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2562) | Cahier de la communauté d'Aubagne (Sénéchaussée d'Aix) | identity_ambigu, boundary_not_certified |
| 6 | [2568](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2568) | Cahier de la communauté de Beaurecueil (Sénéchaussée d'Aix) | V2_boundary_disagreement, boundary_not_certified |
| 6 | [2569](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2569) | Cahier de la communauté de Belcodène (Sénéchaussée d'Aix) | identity_non_retrouve, boundary_not_certified |
| 6 | [2576](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2576) | Cahier de la communauté de Carri et le Rouet (Sénéchaussée d'Aix) | identity_non_retrouve, boundary_not_certified |
| 6 | [2589](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2589) | Cahier de la paroisse de Gréasque (Sénéchaussée d'Aix) | identity_non_retrouve, contradiction_or_observed_error, boundary_not_certified |
| 6 | [2594](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2594) | Cahier de la communauté de Lauris (Sénéchaussée d'Aix) | identity_non_retrouve, boundary_not_certified |
| 6 | [2608](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2608) | Cahier de la communauté de Mayrargues (Sénéchaussée d'Aix) | identity_ambigu, boundary_not_certified |
| 6 | [2609](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2609) | Cahier de la communauté de Merindol (Sénéchaussée d'Aix) | V2_boundary_disagreement, boundary_not_certified |
| 6 | [2611](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2611) | Cahier de la communauté de Mimet (Sénéchaussée d'Aix) | identity_ambigu, boundary_not_certified |
| 6 | [2615](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2615) | Cahier de la communauté de Naux (Sénéchaussée d'Aix) | identity_non_retrouve, boundary_not_certified |
| 6 | [2617](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2617) | Cahier de la communauté de Peipin (Sénéchaussée d'Aix) | identity_ambigu, boundary_not_certified |
| 6 | [2625](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2625) | Cahier de la communauté de Pourrières (Sénéchaussée d'Aix) | identity_ambigu, boundary_not_certified |
| 6 | [2628](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2628) | Cahier de la communauté de Puyvert (Sénéchaussée d'Aix) | identity_ambigu, boundary_not_certified |
| 6 | [2636](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2636) | Cahier de la communauté de Roqueshautes (Sénéchaussée d'Aix) | identity_ambigu, boundary_not_certified |
| 6 | [2648](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2648) | Cahier de la communauté de Saint-Paul-le-Lougassier (Sénéchaussée d'Aix) | identity_ambigu |
| 6 | [2650](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2650) | Cahier de la communauté de Saint-Victoret (Sénéchaussée d'Aix) | identity_ambigu, contradiction_or_observed_error, boundary_not_certified |
| 6 | [2651](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2651) | Cahier de la communauté de Saint-Zacharie (Sénéchaussée d'Aix) | identity_ambigu, contradiction_or_observed_error |
| 6 | [2652](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2652) | Cahier de la sénéchaussée de Saunes (Sénéchaussée d'Aix) | identity_ambigu, contradiction_or_observed_error |
| 6 | [2653](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2653) | Cahier de la communauté de Silans (Sénéchaussée d'Aix) | identity_ambigu, contradiction_or_observed_error, boundary_not_certified |
| 6 | [2656](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2656) | Cahier de la communauté de Tholonet (Sénéchaussée d'Aix) | identity_ambigu, contradiction_or_observed_error, boundary_not_certified |
| 6 | [2657](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2657) | Cahier de la communauté de Tretz (Sénéchaussée d'Aix) | identity_ambigu, contradiction_or_observed_error, boundary_not_certified |
| 6 | [2661](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2661) | Cahier de la communauté de Vellaux (Sénéchaussée d'Aix) | identity_ambigu, V2_boundary_disagreement |
| 6 | [2689](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2689) | Procès verbal de l'assemblée du baillage de Bar-le-Duc | identity_non_retrouve, boundary_not_certified |
| 6 | [2770](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2770) | Doléances des habitants du mont Jura (Baillage d'Aval) | identity_non_retrouve, boundary_not_certified |
| 6 | [2775](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2775) | Annexe aux cahiers des sénéchaussées de Tulle, Brive et Uzerche (Sénéchaussée d'Urzerche) | identity_non_retrouve, boundary_not_certified |

La liste intermédiaire complète est conservée dans `review-queue.jsonl` avec titre, volume, ID et motifs ; filtrer `priority == "intermediaire"`. Les vérifications Codex déjà réalisées sont consultables dans `annotations.jsonl`. Aucune validation humaine nouvelle ni durée humaine mesurée.
