"""Jugements exploratoires saisis après lecture ; aucune règle lexicale de notation.

Les groupes sont des décisions explicites sur des identifiants, non un classifieur.
Les refus restants sont matérialisés dans annotations.json et liés au pool figé.
"""

from common import HERE, read, rows, sha, write

# Chaque groupe : note, identifiants examinés, justification documentaire.
DECISIONS = {
    "q01": [
        (
            3,
            "h024 h067 h103 m104 m111 m116 m120 m132 m147",
            "Baisse ou suppression d'un prélèvement explicitement demandée ; m111 répond directement par le refus de baisser.",
        ),
        (
            2,
            "h008 h046 h048 h061 h077 h079 h081 h118 h137 h153 h187 h199 h228 h230 h246 h253 h259 h261 m097 m107 m118 m138 m146 m151 m172",
            "Réforme, répartition ou emploi de l'impôt, sans baisse globale équivalente ; un impôt unique ne garantit pas un montant moindre.",
        ),
        (
            1,
            "h016 h136 h241 m234",
            "Consentement, service de milice ou dépenses sociales : lien économique indirect, pas une proposition de baisse fiscale.",
        ),
    ],
    "q02": [
        (
            3,
            "h048 h062 h079 h080 h081 h110 h144 h153 h199 h225 h228 h246 h253 h255 h259 m108 m115 m127 m131 m139 m146 m148",
            "Répartition équitable, universalité ou progressivité des prélèvements explicitement discutée.",
        ),
        (
            2,
            "h024 h187 m097 m110 m133 m134 m138 m149 m159",
            "Fiscalité et réforme de perception, fraude, information ou taux ciblés ; ne répond pas aussi directement à la répartition entre contribuables.",
        ),
        (
            1,
            "h063 m113 m232",
            "Dette, bénéfices salariaux ou temps de travail : égalité/finances très générale, pas répartition fiscale.",
        ),
    ],
    "q03": [
        (
            3,
            "h023 h064 h078 h082 h087 h126 h133 h134 h251 m019 m114 m123 m149 m150",
            "Comptes, publicité, vérification ou contrôle des deniers publics explicitement demandés.",
        ),
        (
            2,
            "h029 h061 h077 h095 h127 h199 h260 m042 m107 m228 m230",
            "Économie budgétaire, représentation ou responsabilité administrative ; préoccupation voisine sans contrôle citoyen détaillé.",
        ),
        (
            1,
            "h009 h016 h019 h022 h065 h068 h071 h079 h178 h246 m026 m045 m110 m134 m234",
            "Loi, impôt, dépenses ou responsabilité générale ; pas de contrôle des dépenses publiques dans ce passage.",
        ),
    ],
    "q04": [
        (
            3,
            "h032 h081 h157 h199 h229 m151",
            "Abolition ou réforme de droits exclusifs/exemptions et avantages de statut explicitement discutée.",
        ),
        (
            2,
            "h010 h011 h024 h084 h105 h137 h168 h170 h201 h239 h241 h253 h255 h267 h269 m024 m026 m042 m087",
            "Privilèges de groupe, institutions ou inégalités apparentées ; certains demandent au contraire de conserver leurs exemptions (h084) ou le vote par ordre.",
        ),
        (
            1,
            "h026 h072 h138 h156 h202 h236 h262 m019 m028 m036 m043 m064 m072 m073 m157 m189 m193 m209",
            "Abus, réforme ou égalité très large ; sans demande ciblée sur les privilèges.",
        ),
    ],
    "q05": [
        (
            3,
            "h155 h147",
            "Égalité des peines ou garanties contre la justice arbitraire explicitement demandées ; h147 décrit les garanties de défense.",
        ),
        (
            2,
            "h004 h023 h031 h085 h138 h149 h170 h242 h263 m064 m215",
            "Réforme judiciaire, frais, droits ou garanties proches ; pas nécessairement égalité des traitements selon le statut.",
        ),
        (
            1,
            "h007 h011 h019 h045 h048 h081 h108 h110 h127 h199 h236 h255 h259 m024 m043 m073 m077 m110 m115 m131 m133 m134 m139 m205 m207 m211",
            "Justice au sens large, égalité fiscale/sociale ou mot isolé ; distinguer ces thèmes de l'égalité judiciaire.",
        ),
    ],
    "q06": [
        (
            3,
            "h031 h085 h138 h197 h263",
            "Gratuité de la justice, réduction des frais ou procédures moins dispendieuses explicitement demandées.",
        ),
        (
            2,
            "h009 h052 h147 h170 h247",
            "Simplification de procédures ou juridictions, effet possible sur l'accès à la justice sans baisse des frais aussi explicite.",
        ),
        (
            1,
            "h024 h067 h086 h087 h137 h159 h161 h199 h202 h254 h255 m019 m037 m042 m064 m068 m073 m077 m110 m113 m139 m151 m193 m215 m230",
            "Dépenses, tribunaux ou justice évoqués indirectement ; pas une baisse documentée du coût des procès.",
        ),
    ],
    "q07": [
        (
            3,
            "h023 h082 h087 h126 h133 m026 m045 m050 m071 m085",
            "Compte rendu, responsabilité, révocation ou sanctions des représentants/gouvernants ; h023/h133 concernent des ministres, fonction différente du député.",
        ),
        (
            2,
            "h011 h015 h095 h242 m019 m037 m041 m042 m063 m068 m089 m114 m150 m228",
            "Mandat, contrôle administratif, participation ou transparence ; lien réel mais pas toujours reddition des comptes des élus.",
        ),
        (
            1,
            "h013 h022 h033 h071 h086 h088 h129 h143 h144 h145 h147 h150 h161 h181 h254 h259 h260",
            "Représentation, loi ou finances sans exigence explicite de reddition des comptes.",
        ),
    ],
    "q08": [
        (
            3,
            "h005 h014 h023 h147 h240 h251 m021 m050 m059 m215",
            "Restriction de l'arbitraire, responsabilité, contrôle des malversations ou des abus explicites.",
        ),
        (
            2,
            "h006 h008 h010 h011 h019 h026 h060 h080 h128 h132 h136 h138 h151 h159 h192 h242 m020 m026 m042 m044 m064 m085",
            "Règles, garanties ou mesures de contrôle voisines ; h026 demande une répression religieuse, pas une liberté moderne.",
        ),
        (
            1,
            "h043 h206 h208 m072 m073 m092 m163 m166 m184 m189 m201",
            "Discipline, action publique ou réforme générale ; sans mécanisme pertinent de limitation du pouvoir.",
        ),
    ],
    "q09": [
        (
            3,
            "m079 m103 m197",
            "Décentralisation du service public, maintien des petits établissements ou desserte locale explicites.",
        ),
        (
            2,
            "h242 h266 h269 m014 m020 m054 m069 m101 m141",
            "Organisation municipale, accès territorial, interlocuteurs ou établissements ; proximité seulement partielle ou indirecte.",
        ),
        (
            1,
            "h019 h025 h027 h031 h033 h044 h071 h079 h081 h088 h093 h095 h099 h100 h103 h105 h107 h119 h180 h228 h255 h259 h263 h265 m026 m037 m043 m045 m050 m085 m104 m125 m147 m150 m166",
            "Vie locale, administration ou services au sens large ; pas rapprochement géographique des services dans ce passage.",
        ),
    ],
    "q10": [
        (
            3,
            "h023 h058 h132 h159",
            "Liberté de la presse explicitement revendiquée, avec les réserves historiques réellement exprimées.",
        ),
        (
            2,
            "h026 m064 m065",
            "Expression et ses restrictions : poursuites d'écrivains ou régulation en ligne, vote comme expression ; propositions différentes, voire opposées à la liberté recherchée.",
        ),
        (
            1,
            "h004 h010 h025 h033 h037 h044 h057 h128 h131 h154 h158 h162 m042 m043 m048 m052 m072 m090 m098 m134",
            "Libertés, religion, participation ou confidentialité : ne pas confondre avec liberté de parole/presse.",
        ),
    ],
    "q11": [
        (
            3,
            "h073 h075 h202 m024 m025 m119 m126 m165",
            "Secours, ressources pour pauvres, revenu universel, aide matérielle, logement ou énergie accessibles explicitement proposés ; h202 comporte un stéréotype antisémite conservé, non validé par la note.",
        ),
        (
            2,
            "h099 h226 h239 h241 h269 m009 m014 m017 m049 m103 m145 m234",
            "Difficultés économiques, règles d'assistance ou accès aux secours ; certaines réponses veulent au contraire réduire l'aide (h099/m049/m234).",
        ),
        (
            1,
            "h024 h037 h068 h105 h118 h120 h144 h169 h172 h230 m073 m131 m205",
            "Économie, agriculture ou public fragile seulement à distance ; pas un dispositif de secours aux pauvres.",
        ),
    ],
    "q12": [
        (
            3,
            "h016 h022 h030 h047 h060 h061 h136 h250 h260",
            "Autorité et consentement à créer/percevoir l'impôt explicitement désignés.",
        ),
        (
            2,
            "h062 h128 h129 h134 h187 h212 h228 h246 h259 m108 m109 m111 m117 m146 m148",
            "Organisation fiscale, vote ou assujettissement ; pas même demande sur l'autorité créatrice de l'impôt.",
        ),
        (
            1,
            "h008 h046 h079 h081 m091 m113 m118 m134 m169",
            "Perception, répartition, institutions ou action publique générale ; question de la création non traitée.",
        ),
    ],
    "q13": [
        (3, "h067 h169 h177 h231", "Abolition de la gabelle explicitement demandée."),
        (
            2,
            "h084 h227 h253",
            "Exemption locale, cherté/contrainte de la gabelle ou suppression générale de prélèvements ; pas abolition nationale aussi explicite.",
        ),
        (
            1,
            "h088 h164 h167 h170 h171 h175 h188 h228 h241 h243 m104 m152",
            "Autres droits, obligations ou taxes ; pas le prélèvement sur le sel.",
        ),
    ],
    "q14": [
        (
            3,
            "h074 h091 h104",
            "Taille explicitement concernée, répartition ou assujettissement concret.",
        ),
        (
            2,
            "h048 h062 h079 h080 h081 h110 h117 h153 h214 h224 h225 h228 h255 h259 m115",
            "Répartition fiscale générale ou constat du poids de la taille ; ne pas identifier les impôts modernes à la taille.",
        ),
        (
            1,
            "h036 m037 m073 m086 m091 m113 m219 m232",
            "Répartition d'élus, de bénéfices ou du travail ; lien superficiel avec répartir.",
        ),
    ],
    "q15": [
        (3, "h183 h199 h229 m127", "Exemptions ou niches fiscales explicitement remises en cause."),
        (
            2,
            "h024 h067 h084 h088 h101 h102 h118 h137 h157 h165 h168 h172 h182 h230 h253 m097 m104 m111 m113 m116 m120 m132 m134 m147 m151 m203",
            "Réforme fiscale/droits de groupe ; h084 et h137 maintiennent des privilèges, ce qui n'est pas une abolition équivalente.",
        ),
        (
            1,
            "h032 h147 h170 h241 h267 m019 m072 m076 m089 m138",
            "Privilèges judiciaires, milice, chasse ou avantage général ; pas exemption fiscale.",
        ),
    ],
    "q16": [
        (
            3,
            "h016 h022 h030 h045 h047 h060 h061 h136 h143 h250 h260",
            "Consentement fiscal par la nation/les États généraux explicitement formulé.",
        ),
        (
            2,
            "h062 h081 h144 h205 h212 h259 m108 m109 m131",
            "Répartition et paiement des impôts ; ne pas confondre contribuable et autorité consentante.",
        ),
        (
            1,
            "m113 m134 m228 m229",
            "Finances, représentation ou travail, sans décision de consentement fiscal.",
        ),
    ],
    "q17": [
        (
            3,
            "h088 h184 h232",
            "Suppression de la corvée explicitement demandée ; h232 conserve l'exception des chemins.",
        ),
        (
            2,
            "h153 h214",
            "Conversion de la corvée en argent ou plainte d'en payer sans chemins ; demande différente de sa suppression totale.",
        ),
        (
            1,
            "h067 h076 h147 h164 h167 h168 h169 h170 h171 h228 h238 h241 h253 m104 m152 m230",
            "Autres suppressions de taxes, droits ou obligations ; pas corvée.",
        ),
    ],
    "q18": [
        (
            3,
            "h088 h102 h146 h165 h170 h171 h175 h267",
            "Suppression de droits, justice, prérogatives de chasse ou redevances seigneuriales ; h088 distingue les droits à racheter.",
        ),
        (
            2,
            "h032 h147 h164 h167 h168 h196 h211 h228",
            "Institutions, redevances ou suppression d'une autre obligation ; ni tous les droits ni même titulaires nécessairement seigneuriaux.",
        ),
        (
            1,
            "h019 h024 h122 m032 m056 m072 m073 m076 m089 m104 m138 m152",
            "Monarchie, fiscalité ou suppression en général ; pas droits seigneuriaux.",
        ),
    ],
    "q19": [
        (
            2,
            "m103",
            "Embaucher des professeurs et maintenir des écoles rurales peut concerner les capacités scolaires, sans demande explicite sur les effectifs par classe.",
        ),
        (
            1,
            "m004 m010 m012 m129 m182 m183 m201 m205 m218",
            "Éducation, école ou enfants seulement ; aucun objectif explicite d'effectif par classe.",
        ),
    ],
    "q20": [
        (
            3,
            "h026 h027 h043 h191 h242 m028 m036 m044 m060 m090 m092 m181",
            "Police, mœurs, sécurité, incivilités ou cohésion civile : réponse directe à l'ordre public, avec conceptions répressives/religieuses distinctes des normes contemporaines.",
        ),
        (
            2,
            "h025 h033 h044 h057 h085 h251 m043 m069 m101 m215",
            "Protection civile, justice, religion ou contrôle administratif proches, sans dispositif d'ordre public aussi direct.",
        ),
        (
            1,
            "h010 h011 h014 h019 h021 h023 h045 h081 h094 h119 h128 h129 h135 h248 h256 m020 m056 m079 m166",
            "Ordres sociaux, administration ou institutions ; ne répond pas au maintien de la paix publique.",
        ),
    ],
    "q21": [
        (
            3,
            "h013 h086 h095 h119 h150 m032 m033 m035 m037 m050 m063 m086 m098",
            "Composition/représentativité des assemblées ou porte-parole explicitement discutée ; institutions historiques conservées comme telles.",
        ),
        (
            2,
            "h015 h019 h023 h055 h082 h127 h133 h257 h260 m042 m088",
            "Souveraineté, constitution, compte rendu ou participation politique ; pas désignation aussi directe des représentants.",
        ),
        (
            1,
            "h001 h007 h147 h181",
            "Nation, droit ou milice évoqués sans réponse sur sa représentation.",
        ),
    ],
    "q22": [
        (3, "m134 m188", "Coopération internationale/européenne explicitement demandée."),
        (
            1,
            "h011 h013 h019 h022 h028 h036 h037 h043 h054 h055 h070 h071 h073 h076 h078 h079 h082 h086 h095 h107 h108 h114 h119 h127 h129 h133 h152 h155 h199 h257 h260 m003 m014 m164 m169 m194 m214 m221 m222 m226 m228 m232",
            "États généraux/provinciaux ou collaboration interne : proximité de mots/institutions, sans coopération entre pays souverains.",
        ),
    ],
    "q23": [
        (
            3,
            "h103 h201 h241 m127 m128 m132",
            "Réduction explicite de prélèvements ou dépenses pesant sur les familles ; rachat de cens qui ruinent les familles ou suppression de milice qui les prive de soutien.",
        ),
        (
            2,
            "h009 h024 h031 h067 h075 h079 h081 h101 h110 h117 h118 h137 h138 h153 h187 h199 h205 h253 h255 m087 m107 m129 m135 m155 m159 m160 m169 m210 m230 m233 m234",
            "Charges économiques/fiscales et aides abordées ; certaines réponses diminuent au contraire les aides ou ne visent pas spécifiquement la famille.",
        ),
        (
            1,
            "h070 h112 h135 h247 m019 m021 m073 m163",
            "Charges d'offices, fonctionnement de l'État ou autre difficulté ; ne pas transformer toute charge en coût des ménages.",
        ),
    ],
    "q24": [
        (
            2,
            "m030",
            "Mention explicite de discriminations envers les femmes, mais aucune mesure de représentation politique.",
        ),
        (
            1,
            "h010 h011 h013 h015 h019 h023 h024 h031 h061 h082 h086 h088 h089 h095 h110 h138 h144 h145 h147 h150 h170 h181 h241 h267 m014 m019 m037 m042 m045 m060 m063 m068 m072 m073 m086 m098 m107 m135 m148 m150 m163 m189 m210 m230",
            "Représentation, femmes/veuves ou politique au sens large ; h019 exclut les femmes de la succession royale, sans répondre à leur participation politique contemporaine.",
        ),
    ],
    "q25": [
        (
            1,
            "h093 h105 h215 h266 m112 m163 m176 m187 m189 m197 m199 m202 m210 m211 m221",
            "Infrastructure territoriale, transports, fibre de bois ou développement local ; aucune fibre optique.",
        )
    ],
    "q26": [
        (
            2,
            "m064",
            "Internet, levée d'anonymat et régulation : même préoccupation de données/identité en ligne, proposition différente voire opposée à leur protection.",
        ),
        (
            1,
            "h004 h005 h007 h023 h033 h044 h055 h057 h059 h086 h095 h130 h131 h132 h145 h147 h158 h159 h173 h242 h251 h252 h258 h269 m020 m042 m047 m069 m073 m090 m119 m128 m140 m142 m150 m153 m154 m226",
            "Libertés, secret postal, protection sociale ou administration numérique : pas de données personnelles sur les réseaux sociaux.",
        ),
    ],
    "q27": [
        (
            3,
            "m210",
            "Critique explicite des incitations et de la voiture électrique : répond négativement à la politique envisagée, sans équivalence historique.",
        ),
        (
            2,
            "m106 m155 m158 m159 m165 m176 m195 m202 m212 m236",
            "Aides écologiques, coûts d'achat, recharge ou mobilité électrique ; ne réclame pas nécessairement une subvention à l'achat du véhicule.",
        ),
        (
            1,
            "h037 h265 m113 m127 m151 m167 m199 m203 m209",
            "Agriculture, voitures de roulage ou environnement en général ; aucun véhicule électrique historique.",
        ),
    ],
    "q28": [
        (
            1,
            "h004 h005 h006 h023 h026 h031 h033 h034 h043 h044 h072 h132 h138 h158 h173 h206 h220 h221 h223 h236 h238 h242 h262 h269 m009 m026 m042 m043 m047 m048 m064 m069 m073 m087 m134 m151 m157 m163 m188 m189 m193 m215 m219",
            "Protection, attaque religieuse, dégâts agricoles, fraude, Internet ou réforme : aucun dispositif contre une cyberattaque.",
        )
    ],
    "q29": [
        (
            1,
            "h027 m010 m012 m040 m042 m064 m103 m127 m138 m151 m182 m183 m184 m189 m193 m199 m201 m211 m218 m225",
            "École, formation, Internet ou téléphone marketing évoqués ; pas usage des smartphones en classe.",
        )
    ],
    "q30": [
        (
            1,
            "h028 h070 h080 h086 h107 h129 h144 h152 h176 h180 h208 h242 h254 m008 m015 m022 m073 m112 m163 m188 m189 m211 m214 m221",
            "Organisation ou déploiement au sens général, administration en ligne et infrastructures ; pas réseau mobile 5G.",
        )
    ],
}

EXTRA = [
    (
        "q01",
        "h204",
        3,
        "Modération des impositions demandée explicitement ; témoin positif vérifié hors du pool initial.",
    ),
    (
        "q01",
        "h211",
        3,
        "Diminution des droits sur vin et boissons explicitement demandée ; témoin positif hors pool.",
    ),
    (
        "q06",
        "h269",
        3,
        "Défense indépendante et sans paiement des petites communautés : accès économique à la justice, hors pool.",
    ),
    (
        "q09",
        "h254",
        3,
        "Bureaux de district pour recours plus facile et moins dispendieux : proximité administrative, hors pool.",
    ),
    (
        "q11",
        "h209",
        2,
        "Baisse du prix du pain, besoin essentiel et aide économique indirecte ; hors pool.",
    ),
    (
        "q18",
        "h185",
        3,
        "Modération des droits féodaux aux mutations : réponse directe, distincte d'une abolition totale ; hors pool.",
    ),
]

# Seconde lecture des faux amis et des domaines numériques : garder la note 1
# pour une préoccupation réellement voisine, pas pour n'importe quel mot commun.
REVISIONS = {
    ("q05", "h147"): (
        2,
        "Garanties de défense et d'audition ; proximité judiciaire réelle, pas égalité explicite des peines/statuts.",
    ),
    ("q08", "h026"): (
        0,
        "Poursuivre les écrivains antireligieux est ici une demande de répression ; aucun contrôle des abus de gouvernants.",
    ),
    ("q02", "m133"): (
        3,
        "L'inégalité du prélèvement est explicitement désignée comme le principal problème fiscal.",
    ),
    ("q20", "h191"): (
        2,
        "Police des domestiques et ouvriers : réglementation sociale/rurale, pas dispositif explicite de sécurité générale.",
    ),
    ("q27", "m155"): (
        1,
        "Aides pour isoler le logement et une énergie propre ; pas achat d'automobile.",
    ),
    ("q27", "m159"): (1, "Aides fiscales aux équipements du logement ; pas achat d'automobile."),
}
STRICT_REJECTIONS = {
    "q22": "h011 h013 h019 h022 h028 h036 h037 h043 h054 h055 h070 h071 h073 h076 h078 h079 h082 h086 h095 h107 h108 h114 h119 h127 h129 h133 h152 h155 h199 h257 h260",
    "q26": "h004 h005 h007 h033 h044 h055 h057 h059 h086 h095 h130 h131 h132 h145 h147 h159 h173 h242 h251 h252 h258 h269 m020 m047 m069 m073 m090 m119 m128 m140 m142 m150 m154 m226",
    "q28": "h004 h005 h006 h023 h026 h031 h033 h034 h043 h044 h072 h132 h138 h173 h206 h220 h221 h223 h236 h238 h242 h262 h269 m009 m026 m042 m043 m047 m048 m069 m073 m087 m134 m151 m157 m163 m188 m189 m193 m215 m219",
    "q29": "h027 m042 m127 m138 m151 m184 m189 m193 m199 m211 m225",
    "q30": "h028 h070 h080 h086 h107 h129 h144 h152 h176 h180 h208 h242 h254 m008 m015 m073 m112 m163 m188 m189 m211 m214 m221",
}

# Calibration conservatrice par lecture de l'intention précise : une simple
# famille thématique (impôt / justice / institutions) ne suffit pas à la note2.
CONTENT_REVISIONS = [
    (
        "q03",
        "h127 h260",
        1,
        "Consentement fiscal ; ne décrit aucun contrôle de l'emploi des dépenses.",
    ),
    (
        "q04",
        "h105 h168 m024",
        1,
        "Douanes ou revenu universel sans droit de statut/exclusif explicitement mis en cause.",
    ),
    (
        "q07",
        "m037 m063 m068",
        1,
        "Mode de représentation ou vote ; aucun compte rendu ni sanction des représentants.",
    ),
    (
        "q09",
        "m054 m069 m101 m141",
        1,
        "Qualité ou financement de service public sans proposition de proximité territoriale.",
    ),
    (
        "q11",
        "m009",
        1,
        "Interlocuteurs administratifs disponibles, sans dispositif visant la pauvreté.",
    ),
    (
        "q12",
        "m108 m109 m111 m117 m146 m148",
        1,
        "Qui paie ou quel impôt ; ne répond pas à qui peut décider de le créer.",
    ),
    (
        "q15",
        "h067 h118 h165 h168 h172 h230 m104 m116 m120 m132 m147 m203",
        1,
        "Modification d'un prélèvement ou d'un taux, sans suppression d'une exemption de statut ; fiscalité seule trop générale.",
    ),
    (
        "q16",
        "h062 h081 h144 h205 h212 h259 m108 m109 m131",
        1,
        "Répartition ou assujettissement : payer un impôt n'est pas consentir collectivement à sa création.",
    ),
    (
        "q18",
        "h168 h196 h211",
        1,
        "Douanes, milice ou droits du vin sans qualification seigneuriale dans le passage.",
    ),
    (
        "q20",
        "h033 m069",
        1,
        "Liberté individuelle ou qualité des établissements ; ordre public seulement indirect.",
    ),
    ("q20", "m101", 0, "L'hôpital public : aucun propos sur la paix ou la sécurité publique."),
    (
        "q21",
        "h127 h133",
        1,
        "Souveraineté fiscale ou responsabilité ministérielle, sans identification de ceux qui représentent la nation.",
    ),
    (
        "q24",
        "m030",
        1,
        "Discrimination envers les femmes sans demande de représentation politique ; proximité trop large.",
    ),
    (
        "q27",
        "m158 m165 m195",
        1,
        "Aides au chauffage, transports collectifs ou écologie générale ; aucune aide à acheter une voiture électrique.",
    ),
]
for _qid, _ids, _grade, _reason in CONTENT_REVISIONS:
    for _short in _ids.split():
        REVISIONS[_qid, _short] = (_grade, _reason)


def main():
    pool = rows(HERE / "data/review-pool.jsonl")
    corpus = {d["short_id"]: d for d in rows(HERE / "data/corpus.jsonl")}
    questions = {q["id"]: q for q in read(HERE / "queries.json")["queries"]}
    decisions = []
    explicit = {}
    unused = []
    for qid, groups in DECISIONS.items():
        eligible = {r["document"]["short_id"] for r in pool if r["query"]["id"] == qid}
        for group_grade, ids, group_reason in groups:
            for short in ids.split():
                assert (qid, short) not in explicit
                grade, reason = REVISIONS.get((qid, short), (group_grade, group_reason))
                if short in STRICT_REJECTIONS.get(qid, "").split():
                    grade, reason = (
                        0,
                        "Faux ami ou domaine distinct : aucun élément répondant à l'intention précise « "
                        + questions[qid]["intent"]
                        + " » ; ne pas assimiler l'institution/mot historique à la technologie ou institution contemporaine.",
                    )
                if short not in eligible:
                    unused.append(dict(query_id=qid, short_id=short, grade=grade, reason=reason))
                    continue
                explicit[qid, short] = (grade, reason)
        for short in sorted(eligible):
            grade, reason = explicit.get(
                (qid, short),
                (
                    0,
                    "Le contenu de ce passage ne traite pas de l'intention consignée : "
                    + questions[qid]["intent"],
                ),
            )
            decisions.append(
                dict(
                    query_id=qid,
                    unit_id=corpus[short]["id"],
                    short_id=short,
                    grade=grade,
                    reason=reason,
                    evidence_text=corpus[short]["text"],
                    source="pooled_top10_review",
                    judge="Codex exploratory non-independent",
                )
            )
    assert len(decisions) == len(pool)
    for u in unused:
        short = u["short_id"]
        decisions.append(
            dict(
                query_id=u["query_id"],
                unit_id=corpus[short]["id"],
                short_id=short,
                grade=u["grade"],
                reason=u["reason"],
                evidence_text=corpus[short]["text"],
                source="catalogue_positive_or_contrast_probe",
                judge="Codex exploratory non-independent",
            )
        )
    for qid, short, grade, reason in EXTRA:
        assert (qid, short) not in {(d["query_id"], d["short_id"]) for d in decisions}
        decisions.append(
            dict(
                query_id=qid,
                unit_id=corpus[short]["id"],
                short_id=short,
                grade=grade,
                reason=reason,
                evidence_text=corpus[short]["text"],
                source="targeted_positive_probe_after_pool",
                judge="Codex exploratory non-independent",
            )
        )
    write(
        HERE / "annotations.json",
        dict(
            version=1,
            pool_sha256=sha(HERE / "data/review-pool.jsonl"),
            corpus_sha256=sha(HERE / "data/corpus.jsonl"),
            queries_sha256=sha(HERE / "queries.json"),
            method="Lecture des369 textes uniques du pool avec questions modernes, puis contrôle des ensembles par requête. Lecture complémentaire des61 articles historiques hors pool pour distinguer absence et échec. Notes non indépendantes, pas de score généré par similarité ou lexique. Deuxième lecture plus stricte des faux amis numériques/institutionnels.",
            judgments=decisions,
        ),
    )
    print(f"{len(decisions)} judgments, including {len(EXTRA) + len(unused)} additional probes")


if __name__ == "__main__":
    main()
