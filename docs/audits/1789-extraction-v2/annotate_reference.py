"""Référence déclarative Codex établie sur les packs SOURCE, sans prédictions V2.
Les listes de paragraphes/marqueurs ci-dessous sont des décisions documentaires,
pas des résultats de l'extracteur. Ne pas les recalibrer sur les prédictions.
"""
import datetime
from common import HERE, compact, jlines, read, rows, sha, sources, write

BASE='/TEI.2/text/body/div1/'
def xp(d,n): return BASE+f'div2[{d}]/div3[{n}]'

# Classes des 24 candidats initiaux + une réserve; Albret reste témoin connu.
DECISIONS={
'7f38a827548ffdb56929':('out_of_scope','Albret : cahier explicitement absent; cas négatif déjà connu, exclu du test inédit.'),
'29d69939aa3db58af39f':('out_of_scope','Règlement royal de convocation du Languedoc, non parole revendicative.'),
'95f82f15c28ca8b3e5d6':('out_of_scope','Alsace dix villes : impossibilité explicite de retrouver le cahier.'),
'd7278527a80bb00c83dc':('out_of_scope','Récit des Etats de 1576, hors période.'),
'6acd0da93428676d921b':('autonomous','Revin : cahier local distinct joint au cahier général; plusieurs séries et demandes générales.'),
'54f765d5ea67f23296ad':('out_of_scope','Auxerre : liste nominative annexe à l’assemblée, pas cahier.'),
'e5bdb9bc9c82e58d2532':('autonomous','Caen tiers : cahier collectif, rubriques constitution, subsides, justice, etc.; clôture 21 mars.'),
'9e796d4e3e84a67ab5d1':('autonomous','Blois clergé : cahier en six titres, numérotations de niveaux différents, certifications finales.'),
'b3e97ddf16c84f0129d0':('associated','Grasse : doléance particulière signée du théologal, pièce ecclésiastique individuelle.'),
'26a0b8d4ba30da5eac69':('associated','Dauphiné : pouvoirs et instructions substantiels insérés dans procès-verbaux; pas cahier autonome.'),
'3924aed9efd9451952a8':('autonomous','Bas Limousin noblesse : cahier distinct, article 42 puis signatures fortement corrompues.'),
'f4399dd1b9cec6bf57c4':('autonomous','Courtiches : rédaction collective numérotée en ordinaux avec prolongements non numérotés.'),
'3613b9581134b1302657':('autonomous','Lessart : demandes propres, treize articles, clôture et signatures.'),
'2ab4057d6b29e577acde':('part','Guérande : procès-verbal préparatoire; fin annonce l’insertion du cahier placé dans la division suivante. Le titre seul est trompeur.'),
'93bdb00842fd5759f717':('autonomous','Les Molières : préambule, articles avec sous-listes, signatures et certification.'),
'97ef530c525ea3635153':('autonomous','Bruyère-le-Châtel : rédaction collective, 32 articles, prolongements et signatures.'),
'22896681b17f9fd2d133':('autonomous','Varennes-Saint-Maur : cinq articles et demande finale non numérotée, signatures.'),
'dd6048a2888678726d60':('associated','Soissons : pouvoirs du député et référence à un cahier distinct; pièce associée.'),
'3f06786f2e1ff58c2d1c':('autonomous','Perche tiers : cahier général avec objets locaux Bellême, Mortagne, Nogent; pas trois nouveaux cahiers.'),
'66c2aa5496cd94528a54':('autonomous','Saint-Lambert : huit articles, prolongements aux articles 5 et 6.'),
'38790cedd58205af3e46':('autonomous','La Roque-d’Antheron : cahier collectif numéroté, délégation et signatures.'),
'b005f4d21c87c2df6557':('out_of_scope','Bar : appel nominatif de l’assemblée, pas revendications.'),
'36ccb60628f872dfcd4d':('autonomous','Auriol : cahier de revendications non numérotées, note éditoriale en p ordinaire.'),
'0f512914d7dd276d0e78':('autonomous','Brue : cahier p1–11 puis pièces justificatives à partir de EXTRAIT p12, non nouveaux cahiers.'),
'a2783b5a0cbf7dcfedef':('autonomous','Agimont/Givet : cahier général avec rubriques locales; pas autant de parents que de rubriques.'),
}
# Chaque zone a été lue intégralement; inventaire exhaustif DES DEBUTS dans ces seules zones.
ZONE_PARENTS={
'zone-v2-2':[(xp(12,1),'autonomous',None,None,'Avesnes clergé séculier et régulier; supplément p46–58 lié au corps principal.'),(xp(12,2),'autonomous',None,None,'Avesnes clergé régulier; cahier distinct, annoncé annexé au précédent; conserver relation sans fusion aveugle.')],
'zone-v3-2':[(xp(35,4),'associated',None,None,'Instruction particulière La Rochelle, parallèle au cahier expressément cité.'),(xp(35,5),'associated',None,None,'Pouvoirs de La Rochelle, délégation spéciale; pas cahier autonome.')],
'zone-v4-1':[(xp(18,175),'autonomous',None,None,'Grigny; quatorze articles, signatures et certification.'),(xp(18,176),'autonomous',None,None,'Grisy-et-Suines; dix-huit articles et signatures.')],
'zone-v4-2':[(xp(18,237),'autonomous',None,None,'Mennecy-Villeroy; articles puis demandes non numérotées après Fait.'),(xp(18,238),'autonomous',None,None,'Mériel; huit articles et signatures.')],
'zone-v5-1':[(xp(1,68),'autonomous',None,None,'Saint-Nom-la-Bretèche; six articles; note absorbée dans art1.'),(xp(1,69),'autonomous',None,10,'Saint-Ouen; trois articles et clôture avant CAHIER p10.'),(xp(1,69),'autonomous',10,None,'Saint-Prix; nouveau titre en p10–11, vingt-deux articles et signatures.')],
'zone-v5-2':[(xp(1,54),'autonomous',None,None,'Sainte-Aulde/Chamoust; quatorze articles, retours de page et note en texte.'),(xp(1,55),'autonomous',None,None,'Saint-Jean de Lenville; vingt-deux articles et signatures.')],
'zone-v6-1':[(xp(52,4),'autonomous',None,None,'Enfants Rouges; quarante articles parfois réunis dans un paragraphe.'),(xp(52,5),'autonomous',None,None,'Minimes/place Royale; instructions collectives à vingt-huit articles, protestation finale.')],
}
ZONE_NEGATIVES={
'zone-v1-1':'Règlements de convocation Franche-Comté, Guyenne et Hainaut; aucun début de cahier.',
'zone-v1-2':'Répertoire nominatif alphabétique H/J; aucun début de cahier.',
'zone-v2-1':'Chapitres constitution/législation d’un cahier commencé hors zone; continuations, pas nouveaux parents.',
'zone-v3-1':'Répertoire nominatif Q/R; aucun début de cahier.',
'zone-v6-2':'Répertoire nominatif DD/FF; aucun début de cahier.',
}
# Fenêtres d’articles vérifiées dans les sources ci-dessus; choix explicites avant prédictions.
# triplets: numéro de p de début, p de fin, étiquette originale conceptuelle (pas correction du texte).
ARTICLE_WINDOWS=[
(2,xp(12,1),[(2,2,'1'),(3,3,'2'),(4,4,'3'),(10,13,'9'),(48,49,'supplément 1'),(50,50,'supplément 2')]),
(2,xp(12,2),[(1,1,'1'),(2,2,'2'),(3,3,'3'),(4,4,'4'),(6,6,'6'),(7,8,'7'),(9,9,'8')]),
(4,xp(18,175),[(3,4,'1'),(5,6,'2'),(7,7,'3'),(16,17,'12'),(18,18,'13'),(19,19,'14')]),
(4,xp(18,176),[(1,1,'1'),(2,2,'2'),(6,7,'5'),(10,11,'7'),(20,21,'16'),(23,23,'18')]),
(4,xp(18,237),[(3,3,'1'),(4,4,'2'),(5,5,'3'),(9,9,'7')]),
(4,xp(18,238),[(3,3,'1'),(4,4,'2'),(5,5,'3'),(10,10,'8')]),
(5,xp(1,68),[(2,2,'1'),(3,3,'2'),(4,4,'3'),(5,5,'4'),(6,6,'5'),(7,7,'6')]),
(5,xp(1,69),[(2,2,'Saint-Ouen 1'),(3,3,'Saint-Ouen 2'),(4,5,'Saint-Ouen 3'),(13,13,'Saint-Prix 3'),(24,25,'Saint-Prix 14'),(33,33,'Saint-Prix 22')]),
(5,xp(1,54),[(5,5,'1'),(6,7,'2'),(8,8,'3'),(17,17,'12'),(18,18,'13'),(19,19,'14')]),
(5,xp(1,55),[(2,2,'1'),(3,3,'2'),(4,4,'3'),(15,15,'14'),(23,23,'22')]),
(6,xp(52,4),[(2,2,'1'),(3,3,'2'),(4,4,'3'),(10,11,'13'),(12,12,'14'),(35,35,'40')]),
(6,xp(52,5),[(1,1,'1'),(2,2,'2'),(3,3,'3'),(8,8,'11'),(14,14,'17'),(25,25,'28')]),
]
# Plusieurs articles dans un p: marqueurs et fins explicitement transcrits après lecture.
INLINE=[(5,xp(1,69),12,['Art. 1er.','Art. 2.']), (6,xp(52,4),9,['Art. 8.','Art. 9.','Art. 10-,','Art. 11.','Art. 12.']), (6,xp(52,5),4,['Art. 4.','Art. 5j','Art. 6.','- Art. 7»'])]


def main():
    assert not (HERE/'reference-freeze.json').exists()
    assert not (HERE/'data/validation-v2-predictions.jsonl').exists()
    ss=sources();cands=rows(HERE/'data/validation-candidates.jsonl')+rows(HERE/'data/validation-candidates-reserve.jsonl')
    refs=[]
    for c in cands:
        kind,reason=DECISIONS[c['id'].removeprefix('validation-')]
        refs.append(dict(candidate_id=c['id'],volume=c['volume'],xpath=c['xpath'],classification=kind,reason=reason,novel=c['id']!='validation-7f38a827548ffdb56929',review_scope='source title, opening, short rubrics and closing; not full body collation',parent_ends_certified=False,judge='Codex, non-independent'))
    zrefs=[];parents=[]
    for z in rows(HERE/'data/validation-zones.jsonl'):
        pp=[];s=ss[z['volume']]
        for i,(path,kind,pstart,pnext,reason) in enumerate(ZONE_PARENTS.get(z['id'],[]),1):
            node=s.node(path);a,b=s.span(node)
            anchor=path
            if pstart: anchor=path+f'/p[{pstart}]';a=s.span(s.node(anchor))[0]
            if pnext:b=s.span(s.node(path+f'/p[{pnext}]'))[0]
            p=dict(id=f"gold-{z['id']}-{i}",zone_id=z['id'],volume=z['volume'],xpath=path,anchor_xpath=anchor,start=a,end=b,divisions=[path],classification=kind,reason=reason,review_scope='complete continuous XML zone; original printed page not rechecked',verification='Codex source examination; not independent human')
            pp.append(p);parents.append(p)
        zrefs.append(dict(id=z['id'],volume=z['volume'],start=z['start'],end=z['end'],expected_parent_ids=[p['id'] for p in pp],complete_beginnings_inventory=True,reason=ZONE_NEGATIVES.get(z['id'],'Tous les débuts du texte continu recensés, annexes et rubriques distinguées.'),not_global_recall=True))
    articles=[]
    def save(v,path,a,b,label,selectors):
        s=ss[v]
        while a<b and s.text[a].isspace():a+=1
        while b>a and s.text[b-1].isspace():b-=1
        par=next(p for p in parents if p['volume']==v and p['start']<=a and b<=p['end'])
        articles.append(dict(id='gold-article-'+sha(f'{s.sha256}|{a}|{b}')[:20],volume=v,parent_id=par['id'],start=a,end=b,label=label,xml_selectors=selectors,text=s.text[a:b],status='A',judge='Codex XML boundary review, not independent human',source_sha256=s.sha256))
    for v,path,windows in ARTICLE_WINDOWS:
        for first,last,label in windows:
            selectors=[path+f'/p[{i}]' for i in range(first,last+1)]
            save(v,path,ss[v].span(ss[v].node(selectors[0]))[0],ss[v].span(ss[v].node(selectors[-1]))[1],label,selectors)
    for v,path,pn,markers in INLINE:
        ppath=path+f'/p[{pn}]';a,b=ss[v].span(ss[v].node(ppath));text=ss[v].text[a:b];starts=[text.index(m) for m in markers]
        assert starts==sorted(starts)
        for i,mark in enumerate(markers):save(v,path,a+starts[i],a+starts[i+1] if i+1<len(starts) else b,mark,[ppath])
    jlines(HERE/'data/reference-candidates.jsonl',refs);jlines(HERE/'data/reference-zones.jsonl',zrefs);jlines(HERE/'data/reference-parents.jsonl',parents);jlines(HERE/'data/reference-articles.jsonl',articles)
    write(HERE/'reference-freeze.json',dict(created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),predictions_examined=False,judge='Codex, source examination separated from rule development, NOT independent human or blind trial',candidates=len(refs),novel_candidates=sum(r['novel'] for r in refs),continuous_zones=len(zrefs),parents=len(parents),article_boundaries=len(articles),selection_bias='small deliberately varied hash-stratified sample; partial article windows; no global precision/recall extrapolation',files={n:sha((HERE/n).read_bytes()) for n in ['annotate_reference.py','data/reference-candidates.jsonl','data/reference-zones.jsonl','data/reference-parents.jsonl','data/reference-articles.jsonl','novelty-amendment.json']}))
    print(len(refs),len(parents),len(articles))
if __name__=='__main__':main()
