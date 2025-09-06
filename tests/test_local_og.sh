#!/bin/bash

echo "🧪 Test local des miniatures Open Graph"
echo "========================================"

# Vérifier que le serveur répond
if ! curl -s -f "http://localhost:8000/" > /dev/null; then
    echo "❌ Serveur local non accessible sur http://localhost:8000"
    echo "   Démarrez-le avec : uvicorn app.app:app --host 0.0.0.0 --port 8000 --reload"
    exit 1
fi

echo "✅ Serveur local accessible"

# Test 1 : Métadonnées d'une page de réponse
echo ""
echo "🔍 Test des métadonnées OG/Twitter..."
RESPONSE_ID="398802"
META_OUTPUT=$(curl -s "http://localhost:8000/answers/$RESPONSE_ID" | grep -E "(og:|twitter:|canonical|<title>)")

if echo "$META_OUTPUT" | grep -q "og:type.*article"; then
    echo "✅ og:type = article"
else
    echo "❌ og:type article manquant"
fi

if echo "$META_OUTPUT" | grep -q "og:image.*og/answer/$RESPONSE_ID.png"; then
    echo "✅ og:image dynamique détectée"
else
    echo "❌ og:image dynamique manquante"
fi

if echo "$META_OUTPUT" | grep -q "twitter:card.*summary_large_image"; then
    echo "✅ Twitter Card large image"
else
    echo "❌ Twitter Card manquante"
fi

# Test 2 : Génération d'image
echo ""
echo "🖼️  Test de génération d'image..."
HTTP_CODE=$(curl -s -o /tmp/test_og_local.png -w "%{http_code}" "http://localhost:8000/og/answer/$RESPONSE_ID.png")

if [ "$HTTP_CODE" = "200" ]; then
    if file /tmp/test_og_local.png | grep -q "PNG image data, 1200 x 630"; then
        echo "✅ Image générée avec les bonnes dimensions (1200x630)"
        SIZE=$(stat -c%s /tmp/test_og_local.png)
        echo "   Taille : $SIZE bytes"
    else
        echo "❌ Image générée mais dimensions incorrectes"
    fi
else
    echo "❌ Échec génération image (HTTP $HTTP_CODE)"
fi

# Test 3 : Cache
echo ""
echo "🗄️  Test du cache..."
TIME1=$(curl -s -o /dev/null -w "%{time_total}" "http://localhost:8000/og/answer/$RESPONSE_ID.png")
TIME2=$(curl -s -o /dev/null -w "%{time_total}" "http://localhost:8000/og/answer/$RESPONSE_ID.png")

echo "   Première génération : ${TIME1}s"
echo "   Depuis le cache : ${TIME2}s"

if (( $(echo "$TIME2 < $TIME1" | bc -l) )); then
    echo "✅ Cache fonctionne (plus rapide au 2ème appel)"
else
    echo "⚠️  Cache peut-être pas optimal"
fi

# Test 4 : URL pour les outils sociaux
echo ""
echo "🌐 URLs pour tester avec les outils sociaux :"
echo "   Page : http://localhost:8000/answers/$RESPONSE_ID"
echo "   Image : http://localhost:8000/og/answer/$RESPONSE_ID.png"
echo ""
echo "📝 Pour exposer en public (test outils sociaux) :"
echo "   ngrok http 8000"
echo ""
echo ""
echo "🔍 Test des questions..."

# Test des différents types de questions
QUESTIONS=(
    "35:text"
    "107:single_choice" 
    "112:multi_choice"
)

for q in "${QUESTIONS[@]}"; do
    IFS=':' read -r qid qtype <<< "$q"
    
    echo ""
    echo "  📋 Test question $qtype (ID: $qid)"
    
    # Test de l'image OG
    HTTP_CODE=$(curl -s -o /tmp/test_q_${qid}.png -w "%{http_code}" "http://localhost:8000/og/question/$qid.png")
    
    if [ "$HTTP_CODE" = "200" ]; then
        if file /tmp/test_q_${qid}.png | grep -q "PNG image data, 1200 x 630"; then
            SIZE=$(stat -c%s /tmp/test_q_${qid}.png)
            echo "     ✅ Image générée (${SIZE} bytes)"
        else
            echo "     ❌ Image incorrecte"
        fi
    else
        echo "     ❌ Échec génération (HTTP $HTTP_CODE)"
    fi
    
    # Test des métadonnées (nécessite le slug, on utilise l'ID legacy)
    META_OUTPUT=$(curl -s "http://localhost:8000/questions/$qid" | grep -E "(og:image.*og/question/$qid.png|og:type.*article)")
    
    if echo "$META_OUTPUT" | grep -q "og/question/$qid.png"; then
        echo "     ✅ Métadonnées OG présentes"
    else
        echo "     ❌ Métadonnées OG manquantes"
    fi
    
    rm -f /tmp/test_q_${qid}.png
done

echo ""
echo "🗂️  Test des formulaires..."

# Test des formulaires
FORMS=(
    "1:Grand Débat - Démocratie & citoyenneté"
    "2:Grand Débat - Organisation de l'État & services publics" 
    "3:Grand Débat - Fiscalité & dépenses publiques"
    "4:Grand Débat - Transition écologique"
)

for f in "${FORMS[@]}"; do
    IFS=':' read -r fid fname <<< "$f"
    
    echo ""
    echo "  📋 Test formulaire (ID: $fid)"
    echo "     $fname"
    
    # Test de l'image OG
    HTTP_CODE=$(curl -s -o /tmp/test_f_${fid}.png -w "%{http_code}" "http://localhost:8000/og/form/$fid.png")
    
    if [ "$HTTP_CODE" = "200" ]; then
        if file /tmp/test_f_${fid}.png | grep -q "PNG image data, 1200 x 630"; then
            SIZE=$(stat -c%s /tmp/test_f_${fid}.png)
            echo "     ✅ Image générée (${SIZE} bytes)"
        else
            echo "     ❌ Image incorrecte"
        fi
    else
        echo "     ❌ Échec génération (HTTP $HTTP_CODE)"
    fi
    
    # Test des métadonnées
    META_OUTPUT=$(curl -s "http://localhost:8000/forms/$fid" | grep -E "(og:image.*og/form/$fid.png|og:type.*article)")
    
    if echo "$META_OUTPUT" | grep -q "og/form/$fid.png"; then
        echo "     ✅ Métadonnées OG présentes"
    else
        echo "     ❌ Métadonnées OG manquantes"
    fi
    
    rm -f /tmp/test_f_${fid}.png
done

echo ""
echo "✅ Tests locaux terminés !"

# Cleanup
rm -f /tmp/test_og_local.png