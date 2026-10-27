"""Décisions de lecture Codex explicites; prédictions vues, pas référence humaine indépendante."""
import datetime
from auditlib import HERE,compact,jlines,load_sources,rows,save,sha

BASE='/TEI.2/text/body/div1/'
def xp(d,n):return BASE+f'div2[{d}]/div3[{n}]'
# Identités examinées dans les packs source; aucune identité n’est validée par le seul score.
TARGETS={
1:{1529:(6,1),1531:(6,3),1543:(9,5)},
2:{1559:(1,2),1563:(2,1),1654:(32,1),1568:(3,2),1629:(18,1),1719:(52,3),1674:(28,3),1658:(23,3),1624:(15,10),1597:(12,3),1595:(10,2)},
3:{1795:(1,3),1861:(22,12),1924:(24,3),2043:(52,3),1927:(24,10),1981:(37,3),2033:(50,5),1818:(9,1),1829:(19,1),1803:(2,5),1827:(13,5)},
4:{1745:(1,2),1780:(9,3),2175:(18,145),2291:(18,257),2138:(18,105),2132:(18,99),1847:(18,3),2273:(18,239),2119:(18,88),2200:(18,170),2182:(18,156)},
5:{2333:(1,3),2339:(1,9),2915:(30,1),2828:(9,1),2377:(1,48),2353:(1,24),2920:(32,2),2407:(1,78),2447:(1,118),2406:(1,77)},
6:{2497:(1,4),2508:(3,5),2651:(17,100),2597:(17,45),2582:(17,29),2501:(2,1),2585:(17,32),2503:(2,4),2667:(17,116),2659:(17,108)},
}
NOTES={
1529:'Ouverture du clergé d’Agenois, signatures et protestation de Saint-Caprais; Agen/agenols gêne le score.',
1563:'Trois chapitres consécutifs du clergé d’Anjou, suivis du cahier de la noblesse; pages30–32.',
1654:'Titre Belley/Bellay; art27–28 citent explicitement les curés et décimateurs du Bugey. Changement de désignation territoriale.',
1629:'Procès-verbal: le cahier des griefs est annoncé lu et clos; les paragraphes17–19 contiennent des mandats et renoncements fiscaux. Document associé, pas transcription certifiée du cahier intégral annoncé.',
1658:'La meilleure proposition est la notice du cahier de noblesse introuvable. Le vrai cahier du tiers commence dans div3[3]; une pièce commerciale distincte commence p167.',
1624:'Villiers/Villers-la-Montagne; clôture19mars et collation par LeBlanc, pas un rapprochement géographique automatique.',
1861:'Assemblée municipale de Courtiches et demandes collectives du village, suivies de signatures; pas un corps professionnel.',
1924:'Dossier général des clergés de Grasse/Vence, avec demandes non souscrites p50 et autres pièces particulières; la notice ne donne pas d’identifiant à chacune.',
1981:'Délibération préliminaire div3[2], expressément dite annexée au cahier au début de div3[3]. Le clergé finit p62; p63 ouvre les pouvoirs de la noblesse. Même identité documentaire, proposition de texte incomplète.',
2033:'Le catalogue distingue le cahier de la ville (2493) de celui du tiers (2033). p55 commence le second; les instructions/pouvoirs div3[6] continuent le dossier jusqu’à712.',
2043:'Le corps principal de Melun finit p153, puis Montarlot commence p154 sur la même page750. Le catalogue n’en donne pas ici de notice séparée: portée d’annexe ou sous-document à décider, bornes non certifiées.',
1818:'Sénéchaussée des Lannes dans le texte; collation explicitement à Dax. Les appellations ne se comparent pas littéralement.',
1829:'Mandats de la ville de Dijon, arrêtés les15–17mars; un pouvoir d’un autre cahier sur la même page produit un ex-aequo trompeur.',
1745:'Corps nobiliaire de Mirecourt; demandes de Lorraine et travail des commissaires associés, pages1–6. Ne pas prendre corps pour corps professionnel.',
2291:'Paroisse de Montlhéry et cahier de la ville voisin distinct. Le qualificatif de la notice doit être conservé; pages partagées.',
2182:'Titre OCR très dégradé, suite Fontenay-sous-bois / Fontenay-lès-Brüs / Fontenay-en-Brie compatible; pas de répétition locale lisible dans le contrôle du corps: identité gardée incertaine.',
2200:'Gometz-la-Ville finit p39; CAHIER p40 puis Gonesse p41. La division continue encore avec Gournay; aucune équivalence division=cahier.',
2333:'38 articles, signatures, certification13avril et signature deRosnay; contrôle ancien Pecqueuse.',
2339:'Neuf articles, clôture14avril et signatures de Pierrelez, distincts du cahier Carré voisin sur la même page21.',
2915:'Vrai cahier du clergé de Soissons, distinct de la notice des cahiers de noblesse/tiers absents. Le libellé initial de sélection a été corrigé sans changer l’identifiant.',
2377:'Morsang répété dans le corps et la clôture; Saint-Germain/Morsang distinct de Saint-Germain-Desnoue voisin.',
2823:'Liste nominative de nobles de Poitou, pas cahier: faux positif si le typegriev était pris comme certification de nature.',
2406:'Le procès-verbal de Sarcelles inclut bien les articles des doléances, puis le mandat et les signatures: pas une simple annonce de cahier.',
2503:'La proposition vise les pouvoirs div3[3] du4avril; le cahier effectif est div3[4], délibéré30mars–1avril. La portée du préfixe dans la notice reste ambiguë, la fin de la proposition est certainement trop courte.',
2684:'Liste des comparants nobles d’Autun sous un groupe de listes; ce n’est pas un cahier malgré le typegriev.',
}
# Bornes examinées: contrôles anciens + choix explicites de cas courts et de dossiers difficiles.
BOUNDARY_IDS={1529,1559,1563,1795,1861,1924,1745,1780,2175,2333,2339,2915,2497,2132,2273,2119,2407,2447,2597,2582,2651,2659,2200,2033,1658,1981}


def main():
    assert not (HERE/'annotations-freeze.json').exists()
    ss=load_sources();out=[];preds={r['persee_id']:r for r in rows(HERE/'data/alignment-predictions.jsonl')}
    for m in rows(HERE/'data/metadata.jsonl'):
        v=m['volume'];number=int(m['id'].split('_')[-1]);s=ss[v];pair=TARGETS[v].get(number)
        if not pair:
            out.append(dict(persee_id=m['id'],volume=v,kind='not_cahier',reason=NOTES.get(number,'Notice de table, texte liminaire ou règlement administratif, exclue du corpus de cahiers; ne pas transformer une notice en cahier.'),identity_review='not_evaluated_as_target',reviewer='Codex, non-independent',boundary_reference=None));continue
        path=xp(*pair);node=s.node(path);ps=node.findall('p');a,b=s.span(node);anchor=path;divs=[path];kind='associated_minutes' if number==1629 else 'cahier'
        if number==2033:anchor=path+'/p[55]';a=s.span(s.node(anchor))[0]
        note=NOTES.get(number,'Concordance de l’intitulé avec l’ouverture, les demandes ou la clôture dans le texte source; contrôle des voisins. Corps long non collationné intégralement.')
        uncertain=number in {2182,2503}
        ref=None
        if number in BOUNDARY_IDS:
            if number==1563:divs=[xp(2,i) for i in [1,2,3]];b=s.span(s.node(divs[-1]))[1]
            elif number==1745:divs=[xp(1,i) for i in [2,3,4]];b=s.span(s.node(divs[-1]))[1]
            elif number==2175:divs=[xp(18,i) for i in [145,146,147]];b=s.span(s.node(divs[-1]))[1]
            elif number==2200:b=s.span(s.node(path+'/p[40]'))[0]
            elif number==1658:b=s.span(s.node(path+'/p[167]'))[0]
            elif number==2033:divs.append(xp(50,6));b=s.span(s.node(divs[-1]))[1]
            elif number==1981:a=s.span(s.node(xp(37,2)))[0];divs=[xp(37,2),xp(37,3)];b=s.span(s.node(path+'/p[63]'))[0]
            ref=dict(start=a,end=b,divisions=divs,scope='Stanford document with explicitly associated sections/annexes, per reviewer policy; not exact Persée XML correspondence',examined='source opening/closing and transitions or prior reviewed control; not a full historical collation',status='Codex_XML_boundary_review_not_independent_human')
        primary_anchor=anchor
        acceptable=[anchor]
        if number==1981:acceptable.append(xp(37,2))
        if number==2503:acceptable=[path]  # Powers remain a RELATED piece; not silently accepted as the full cahier.
        out.append(dict(persee_id=m['id'],volume=v,kind=kind,target_xpath=path,target_anchor=primary_anchor,acceptable_identity_anchors=acceptable,identity_review='uncertain' if uncertain else 'examined_compatible_identity',identity_reason=note,reviewer='Codex, sees predictions; non-independent, not blind',reference_text_quotes=[compact(ps[0])[:300],compact(ps[-1])[-300:]],boundary_reference=ref,required_cahier_span=[s.span(node)[0],s.span(node)[1]] if number==2503 else None,source_sha256=s.sha256))
    jlines(HERE/'data/annotations.jsonl',out)
    save(HERE/'annotations-freeze.json',dict(created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),files={f:sha((HERE/f).read_bytes()) for f in ['annotations.py','data/annotations.jsonl']},reviewer='Codex non-independent, predictions visible',boundary_references=sum(r.get('boundary_reference') is not None for r in out),limitation='No Persée full text fetched; cannot certify identity of the producer’s exact intra-page text zones. Source boundaries and document identity are separately annotated.'))
    print(len(out),'notices;',sum(r.get('boundary_reference') is not None for r in out),'boundary references')
if __name__=='__main__':main()
