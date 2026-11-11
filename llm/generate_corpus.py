#!/usr/bin/env python3
"""產生 mini-x 合成多語對話語料到 llm/corpus/gen/。

以「回合模板 + 詞槽」組合出大量五語平行（中英法日韓）對話，
格式與 corpus/MULTILINGUAL.md 相同。中文行會對照 spec.md 的
中文字集做檢查，日文漢字與韓文不符合時只提出警告。

用法：
    python3 llm/generate_corpus.py                  # 全部主題，每主題 300 篇
    python3 llm/generate_corpus.py --per-file 500
    python3 llm/generate_corpus.py --theme weather
"""
import argparse
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GEN_DIR = ROOT / "corpus" / "gen"
SPEC = ROOT.parent / "spec.md"
LANGS = ("中", "英", "法", "日", "韓")


# ---------------------------------------------------------------- 詞槽工具

def V(zh, en, fr, ja, ko):
    """一個詞的五語版本。"""
    return {"中": zh, "英": en, "法": fr, "日": ja, "韓": ko}


def S(s):
    """五語都一樣的值（通常是數字）。"""
    return {"中": s, "英": s, "法": s, "日": s, "韓": s}


def T(zh, en, fr, ja, ko, **slots):
    """一個回合模板；slots 為 詞槽名 -> 候選值清單。"""
    return {"中": zh, "英": en, "法": fr, "日": ja, "韓": ko, "slots": slots}


# ---------------------------------------------------------------- 詞槽庫

def _nums(a, b):
    return [S(str(i)) for i in range(a, b + 1)]

HOURS = _nums(1, 12)
MINUTES = [S(str(i)) for i in range(5, 60, 5)]
MINDUR = [S(str(i)) for i in (5, 10, 15, 20, 30, 40)]
COUNTS = _nums(1, 9)
NUM6 = _nums(2, 6)
NUM20 = _nums(1, 30)
MONTHS = _nums(1, 12)
PRICES = [S(str(i)) for i in (10, 20, 30, 50, 100, 200)]
PHONE_NUMS = [S(f"{a:02d}{b:02d}{c:04d}") for a in (1, 2, 9) for b in (0, 1, 8) for c in (100, 234, 5678)]

PLACES = [
    V("park", "park", "parc", "park", "공원"),
    V("market", "market", "marché", "market", "시장"),
    V("學校", "school", "école", "がっこう", "학교"),
    V("hospital", "hospital", "hôpital", "びょういん", "병원"),
    V("車站", "the station", "la gare", "えき", "역"),
    V("海邊", "the sea", "la mer", "うみ", "바다"),
    V("家", "home", "la maison", "いえ", "집"),
    V("店", "the shop", "la boutique", "みせ", "가게"),
    V("restaurant", "the restaurant", "le restaurant", "レストラン", "식당"),
]
DIRECTIONS = [
    V("東", "east", "est", "ひがし", "동"),
    V("西", "west", "ouest", "にし", "서"),
    V("南", "south", "sud", "みなみ", "남"),
    V("北", "north", "nord", "きた", "북"),
]
FOODS = [
    V("飯", "rice", "du riz", "ごはん", "밥"),
    V("魚", "fish", "du poisson", "さかな", "물고기"),
    V("肉", "meat", "de la viande", "にく", "고기"),
    V("茶", "tea", "du thé", "おちゃ", "차"),
    V("水", "water", "de l'eau", "みず", "물"),
    V("蛋", "eggs", "des œufs", "たまご", "달걀"),
    V("bread", "bread", "du pain", "パン", "빵"),
    V("cake", "cake", "du gâteau", "ケーキ", "케이크"),
    V("水果", "fruit", "des fruits", "くだもの", "과일"),
    V("菜", "food", "de la nourriture", "やさい", "요리"),
]
FAMILY = [
    V("媽媽", "mother", "maman", "おかあさん", "엄마"),
    V("爸爸", "father", "papa", "おとうさん", "아빠"),
    V("哥哥", "brother", "grand frère", "おにいさん", "형"),
    V("姐姐", "sister", "grande sœur", "おねえさん", "누나"),
    V("弟弟", "little brother", "petit frère", "おとうと", "동생"),
    V("朋友", "friend", "ami", "ともだち", "친구"),
    V("老師", "teacher", "professeur", "せんせい", "선생님"),
    V("同學", "classmate", "camarade", "とも", "친구"),
]
WX_NOUN = [
    V("雨", "rain", "de la pluie", "あめ", "비"),
    V("雪", "snow", "de la neige", "ゆき", "눈"),
    V("風", "wind", "du vent", "かぜ", "바람"),
]
COLORS = [
    V("紅", "red", "rouge", "あかい", "빨간"),
    V("藍", "blue", "bleu", "あおい", "파란"),
    V("綠", "green", "vert", "みどり", "초록"),
    V("白", "white", "blanc", "しろい", "하얀"),
    V("黑", "black", "noir", "くろい", "검은"),
]
SEA_COLORS = [COLORS[1], COLORS[2]]
THINGS = [
    V("衣服", "clothes", "des vêtements", "ふく", "옷"),
    V("書", "a book", "un livre", "ほん", "책"),
    V("錢", "money", "l'argent", "お金", "돈"),
    V("電話", "phone", "le téléphone", "でんわ", "전화"),
    V("umbrella", "umbrella", "un parapluie", "かさ", "우산"),
    V("medicine", "medicine", "un médicament", "くすり", "약"),
    V("球", "a ball", "un ballon", "ボール", "공"),
    V("花", "flowers", "des fleurs", "はな", "꽃"),
    V("鳥", "birds", "des oiseaux", "とり", "새"),
]
THINGS_SEE = [THINGS[7], THINGS[8], THINGS[4]]
SUBJECTS = [
    V("國文", "language", "le français", "こくご", "국어"),
    V("數學", "math", "les mathématiques", "さんすう", "수학"),
    V("物理", "physics", "la physique", "ぶつり", "물리"),
    V("音樂", "music", "la musique", "おんがく", "음악"),
    V("畫", "drawing", "le dessin", "え", "그림"),
]

# ---------------------------------------------------------------- 回合模板

FILLERS = [
    T("好。", "Ok.", "Ok.", "いいよ。", "그래."),
    T("是。", "Yes.", "Oui.", "うん。", "그래."),
    T("真的？", "Really?", "Vraiment ?", "ほんとう？", "진짜?"),
    T("謝謝你。", "Thank you.", "Merci.", "ありがとう。", "고마워."),
    T("不用謝。", "No thanks.", "Pas merci.", "いいよ。", "아니에요."),
    T("走吧。", "Let's go.", "Allons-y.", "いこう。", "가자."),
    T("我知道了。", "I know.", "Je sais.", "しってる。", "알아."),
    T("我也是。", "Me too.", "Moi aussi.", "わたしも。", "나도."),
    T("你說吧。", "You say it.", "Dis-moi.", "いって みて。", "말해 봐."),
    T("那好吧。", "Ok then.", "Bon, d'accord.", "じゃ いいよ。", "그럼 그래."),
]

TIME_CHAINS = [
    [
        T("現在幾點了？", "What hour is it now?", "Quelle heure est-il ?", "いま なんじ？", "지금 몇 시야?"),
        T("現在 {h} 點 {m} 分。", "Now it is {h} hour and {m} minute.", "Il est {h} heures {m} minutes.", "いま {h}じ {m}ふん。", "지금 {h}시 {m}분이야.", h=HOURS, m=MINUTES),
        T("我們 {h} 點要去{place}。", "We go to {place} at {h} hour.", "Nous allons à {place} à {h} heures.", "{h}じに {place}へ いきます。", "{h}시에 {place}에 가요.", h=HOURS, place=PLACES),
        T("好。到時候在門口見。", "Ok. See you at the gate then.", "Ok. On se voit à la porte.", "いいよ。 その とき 門で あおう。", "그래. 그때 문 앞에서 보자."),
    ],
    [
        T("今天早上我很忙。", "Today morning I am very busy.", "Ce matin je suis très occupé.", "きょうの あさは とても いそがしい。", "오늘 아침은 정말 바빠."),
        T("是。你今天的事有 {n} 個。", "Yes. You have {n} things today.", "Oui. Tu as {n} choses aujourd'hui.", "うん。 きょうの ことは {n} つ。", "그래. 오늘 할 일이 {n}개 있어.", n=COUNTS),
        T("我要先吃飯。", "I eat first.", "Je mange d'abord.", "まず ごはんを たべる。", "먼저 밥을 먹을게."),
        T("好。飯在這裡。", "Ok. The rice is here.", "Ok. Le riz est ici.", "いいよ。 ごはんは ここ。", "그래. 밥은 여기 있어."),
    ],
    [
        T("今天是幾月幾日？", "What day is it today?", "Quel jour sommes-nous ?", "きょうは なんがつ なんにち？", "오늘이 몇 월 며칠이야?"),
        T("今天是 {mo} 月 {n} 日。", "Today is month {mo}, day {n}.", "Nous sommes le {n} du mois {mo}.", "きょうは {mo} がつ {n} にち。", "오늘은 {mo}월 {n}일이야.", mo=MONTHS, n=COUNTS),
        T("明天我們去{place}吧。", "Tomorrow we go to {place}.", "Demain nous allons à {place}.", "あした {place}へ いこう。", "내일 {place}에 가자.", place=PLACES),
        T("好。早上 {h} 點走。", "Ok. We go at {h} in the morning.", "Ok. On part à {h} heures du matin.", "いいよ。 あさ {h}じに いく。", "그래. 아침 {h}시에 가.", h=HOURS),
    ],
]

WEATHER_CHAINS = [
    [
        T("今天天氣真冷。", "Today is very cold.", "Aujourd'hui il fait très froid.", "きょうは とても さむい。", "오늘은 정말 추워."),
        T("是。風也很大。", "Yes. The wind is very big.", "Oui. Le vent est très fort.", "うん。 かぜも とても 大きい。", "그래. 바람도 아주 세."),
        T("我要穿多一點衣服。", "I want to wear more clothes.", "Je veux mettre plus de vêtements.", "服を もっと きたい。", "나는 옷을 더 입고 싶어."),
        T("好。聽說明天會下雨。", "Ok. I hear it will rain tomorrow.", "Ok. On dit qu'il pleuvra demain.", "いいよ。 あした あめが ふるって。", "그래. 내일 비가 온대."),
    ],
    [
        T("今天天氣真冷。", "Today is very cold.", "Aujourd'hui il fait très froid.", "きょうは とても さむい。", "오늘은 정말 추워."),
        T("是。聽說後天會下雪。", "Yes. I hear it will snow the day after tomorrow.", "Oui. On dit qu'il neigera après-demain.", "うん。 あさって ゆきが ふるって。", "그래. 모레 눈이 온대."),
        T("真的？我最喜歡下雪。", "Really? I like snow the most.", "Vraiment ? J'aime la neige le plus.", "ほんとう？ ゆきが いちばん すきだ。", "진짜? 나는 눈 제일 좋아해."),
        T("那我們到時候出去玩。", "Then we play outside then.", "Alors on jouera dehors.", "じゃ その とき そとで あそぼう。", "그럼 그때 밖에서 놀자."),
    ],
    [
        T("今天很熱。", "Today is very hot.", "Aujourd'hui il fait très chaud.", "きょうは とても あつい。", "오늘은 아주 더워."),
        T("是。sun 很大。", "Yes. The sun is very big.", "Oui. Le soleil est très grand.", "うん。 sunが とても 大きい。", "그래. 해가 아주 커."),
        T("我要多喝水。", "I want to drink more water.", "Je veux boire plus d'eau.", "水を もっと のみたい。", "나는 물을 더 마시고 싶어."),
        T("我也是。天熱要多喝水。", "Me too. When it is hot, drink more water.", "Moi aussi. Quand il fait chaud, bois plus d'eau.", "わたしも。 あつい ときは 水を たくさん のむ。", "나도. 더울 때는 물을 많이 마셔."),
    ],
    [
        T("今天天氣很好。", "Today is very good.", "Aujourd'hui il fait très bon.", "きょうは てんきが とても いい。", "오늘 날씨가 정말 좋아."),
        T("是。天空很藍，雲很少。", "Yes. The sky is very blue. There are few clouds.", "Oui. Le ciel est très bleu. Il y a peu de nuages.", "うん。 そらは とても あおくて、 くもは すこし。", "그래. 하늘이 아주 파래. 구름이 조금 있어."),
        T("我們去{place}走走吧。", "We go to {place} and walk.", "Allons à {place} marcher.", "{place}へ さんぽに いこう。", "{place}에 가서 산책하자.", place=PLACES),
        T("好。坐 bus {min} 分鐘就到。", "Ok. It is {min} minutes by bus.", "Ok. C'est {min} minutes en bus.", "いいよ。 busで {min}ぷん。", "그래. 버스로 {min}분이면 돼.", min=MINDUR),
    ],
]

FOOD_CHAINS = [
    [
        T("我們去吃飯吧。", "We go to eat.", "Allons manger.", "ごはんを たべに いこう。", "밥 먹으러 가자."),
        T("好。想去哪裡吃？", "Ok. Where do you want to eat?", "Ok. Où veux-tu manger ?", "いいよ。 どこで たべたい？", "그래. 어디서 먹고 싶어?"),
        T("去{dir}邊那家店。", "We go to that shop on the {dir} side.", "Allons à la boutique à {dir}.", "{dir}がわの みせへ いこう。", "{dir}쪽 가게로 가자.", dir=DIRECTIONS),
        T("那裡賣什麼？", "What do they sell there?", "Qu'y vendent-ils ?", "そこは なにを うって いる？", "거긴 뭘 파는 거야?"),
        T("賣{f1}、{f2}和 soup。", "They sell {f1}, {f2} and soup.", "Ils vendent {f1}, {f2} et de la soupe.", "{f1}と {f2}と soupを うって いる。", "{f1}랑 {f2}, soup을 팔아.", f1=FOODS, f2=FOODS),
    ],
    [
        T("你想吃什麼？", "What do you want to eat?", "Que veux-tu manger ?", "なにを たべたい？", "뭐 먹고 싶어?"),
        T("我要 {n} 個{f}。", "I want {n} {f}.", "Je veux {n} {f}.", "{f}を {n} つ。", "{f} {n}개.", n=COUNTS, f=FOODS),
        T("我要{f}。還要 1 個飯。", "I want {f}. Also 1 rice.", "Je veux {f}. Et 1 riz.", "{f}が ほしい。 ごはんも 1 つ。", "나는 {f} 먹을래. 밥도 1개.", f=FOODS),
        T("好。我去叫。", "Ok. I go to call.", "Ok. Je vais appeler.", "いいよ。 よぶね。", "그래. 내가 부를게."),
    ],
    [
        T("我吃完了。", "I finished eating.", "J'ai fini de manger.", "たべおわった。", "다 먹었어."),
        T("我也是。很好吃。", "Me too. It was very good.", "Moi aussi. C'était très bon.", "わたしも。 とても おいしかった。", "나도. 정말 맛있었어."),
        T("今天我給錢。", "Today I give the money.", "Aujourd'hui je paie.", "きょうは お金を わたす。", "오늘은 내가 낼게."),
        T("好。下次我給。", "Ok. Next time I give.", "Ok. La prochaine fois je paie.", "いいよ。 つぎは わたしが はらう。", "그래. 다음엔 내가 낼게."),
    ],
]

SHOPPING_CHAINS = [
    [
        T("我要去 market 買{f}。", "I go to market to buy {f}.", "Je vais au marché acheter {f}.", "marketへ {f}を かいに いく。", "나는 market에 {f} 사러 가.", f=FOODS),
        T("好。你要買幾個？", "Ok. How many do you want to buy?", "Ok. Tu en achètes combien ?", "いいよ。 いくつ かう？", "그래. 몇 개 살 거야?"),
        T("我要 {n} 個。你呢？", "I want {n}. And you?", "J'en veux {n}. Et toi ?", "{n} つ。 あなたは？", "{n}개. 너는?", n=COUNTS),
        T("我要 {n2} 個。", "I want {n2}.", "J'en veux {n2}.", "{n2} つ ほしい。", "나는 {n2}개.", n2=COUNTS),
    ],
    [
        T("這個多少錢？", "How much is this?", "Combien ça coûte ?", "これは いくら？", "이거 얼마야?"),
        T("{p} 塊。", "It is {p}.", "C'est {p}.", "{p}えんだよ。", "{p}원이야.", p=PRICES),
        T("有一點貴。那個呢？", "A little expensive. And that one?", "Un peu cher. Et celui-là ?", "ちょっと たかい。 あれは？", "조금 비싸. 저건?"),
        T("那個 {p2} 塊，不貴。", "That one is {p2}. Not expensive.", "Celui-là coûte {p2}. Pas cher.", "あれは {p2}えん。 たかくない。", "저건 {p2}원. 안 비싸.", p2=PRICES),
    ],
    [
        T("這家店真大。", "This shop is very big.", "Cette boutique est très grande.", "この みせは とても 大きい。", "이 가게는 정말 커."),
        T("是。東西很多。", "Yes. There are many things.", "Oui. Il y a beaucoup de choses.", "うん。 ものが たくさん ある。", "그래. 물건이 많아."),
        T("我在找{t}。", "I am looking for {t}.", "Je cherche {t}.", "{t}を さがして いる。", "나는 {t}를 찾고 있어.", t=THINGS),
        T("在那邊。你來看。", "It is there. Come and see.", "C'est là-bas. Viens voir.", "あそこだよ。 きて みて。", "저기 있어. 와서 봐."),
    ],
]

TRANSPORT_CHAINS = [
    [
        T("我們怎麼去{place}？", "How do we go to {place}?", "Comment allons-nous à {place} ?", "{place}へ どう いく？", "{place}에 어떻게 가?", place=PLACES),
        T("坐 bus {n2} 去。", "We take bus {n2}.", "On prend le bus {n2}.", "bus {n2}に のる。", "{n2}번 버스를 타.", n2=NUM20),
        T("要坐多長時間？", "How long does it take?", "Ça prend combien de temps ?", "どのくらい かかる？", "얼마나 걸려?"),
        T("{min} 分鐘。", "{min} minutes.", "{min} minutes.", "{min}ぷん。", "{min}분.", min=MINDUR),
    ],
    [
        T("車站遠嗎？", "Is the station far?", "La gare est loin ?", "えきは とおい？", "역은 멀어?"),
        T("不遠。走 {min} 分鐘就到。", "Not far. {min} minutes on foot.", "Pas loin. {min} minutes à pied.", "とおくない。 あるいて {min}ぷん。", "안 멀어. 걸어서 {min}분.", min=MINDUR),
        T("好。我們走吧。", "Ok. We go.", "Ok. Allons-y.", "いいよ。 いこう。", "그래. 가자."),
    ],
    [
        T("我爸爸開車來了。", "My father comes by car.", "Mon père vient en voiture.", "おとうさんが 車で きた。", "아빠가 차로 왔어."),
        T("好。我們坐車去{place}。", "Ok. We go to {place} by car.", "Ok. Nous allons à {place} en voiture.", "いいよ。 車で {place}へ いこう。", "그래. 차로 {place}에 가자.", place=PLACES),
    ],
]

SCHOOL_CHAINS = [
    [
        T("今天在學校學了什麼？", "What did you learn at school today?", "Qu'as-tu appris à l'école aujourd'hui ?", "きょう がっこうで なにを ならった？", "오늘 학교에서 뭐 배웠어?"),
        T("學了{sub}。", "I learned {sub}.", "J'ai appris {sub}.", "{sub}を ならった。", "{sub}을 배웠어.", sub=SUBJECTS),
        T("難嗎？", "Is it hard?", "C'est difficile ?", "むずかしい？", "어려워?"),
        T("有一點難，不過我喜歡。", "A little hard, but I like it.", "Un peu difficile, mais j'aime ça.", "ちょっと むずかしいけど、 すきだ。", "조금 어렵지만 좋아해."),
    ],
    [
        T("今天老師叫你寫什麼？", "What did the teacher ask you to write today?", "Que t'a demandé d'écrire le professeur ?", "きょう せんせいは なにを かけ といった？", "오늘 선생님이 뭐 쓰래?"),
        T("寫 {n} 個句子。", "Write {n} sentences.", "Écris {n} phrases.", "ぶんを {n} つ かく。", "문장을 {n}개 쓰기.", n=COUNTS),
        T("多嗎？", "Is it many?", "C'est beaucoup ?", "おおい？", "많아?"),
        T("不多。我 30 分鐘就寫完。", "Not many. I finish in 30 minutes.", "Pas beaucoup. Je finis en 30 minutes.", "多くない。 30ぷんで かける。", "많지 않아. 30분이면 써."),
    ],
    [
        T("明天要拿什麼去學校？", "What must we take to school tomorrow?", "Que doit-on apporter à l'école demain ?", "あした なにを がっこうに もって いく？", "내일 학교에 뭐 가져가야 해?"),
        T("要拿{t}和{t2}。", "We take {t} and {t2}.", "On apporte {t} et {t2}.", "{t}と {t2}を もって いく。", "{t}랑 {t2} 가져가.", t=THINGS, t2=THINGS),
        T("好。我記得了。", "Ok. I remember.", "Ok. Je m'en souviens.", "いいよ。 おぼえた。", "그래. 기억했어."),
    ],
]

FAMILY_CHAINS = [
    [
        T("你家人多嗎？", "Is your family big?", "Ta famille est grande ?", "かぞくは おおい？", "네 가족은 많아?"),
        T("有 {n2} 個人。", "We are {n2} people.", "Nous sommes {n2}.", "{n2}にん いる。", "{n2}명이야.", n2=NUM6),
        T("你哥哥在做什麼？", "What does your brother do?", "Que fait ton grand frère ?", "おにいさんは なにを して いる？", "너 형은 뭐 해?"),
        T("他在學校教書。", "He teaches at school.", "Il enseigne à l'école.", "がっこうで おしえて いる。", "학교에서 가르쳐."),
    ],
    [
        T("媽媽在做飯。", "Mother is cooking.", "Maman cuisine.", "おかあさんが ごはんを つくって いる。", "엄마가 밥을 짓고 있어."),
        T("真好。今天有什麼？", "Very good. What is there today?", "Très bien. Qu'y a-t-il aujourd'hui ?", "いいね。 きょうは なに？", "좋다. 오늘 뭐야?"),
        T("有{f}和{f2}。", "There are {f} and {f2}.", "Il y a {f} et {f2}.", "{f}と {f2}が ある。", "{f}랑 {f2} 있어.", f=FOODS, f2=FOODS),
    ],
    [
        T("我要幫媽媽洗衣服。", "I help mother wash clothes.", "J'aide maman à laver les vêtements.", "おかあさんの ふくあらいを たすける。", "나는 엄마 도와서 빨래할 거야."),
        T("好。我也來幫。", "Ok. I come to help too.", "Ok. Je viens aider aussi.", "いいよ。 わたしも たすける。", "그래. 나도 도울게."),
    ],
]

HEALTH_CHAINS = [
    [
        T("你今天怎麼了？", "What is wrong with you today?", "Qu'as-tu aujourd'hui ?", "きょうは どうしたの？", "오늘 왜 그래?"),
        T("我病了，沒有去上學。", "I am sick. I did not go to school.", "Je suis malade. Je ne suis pas allé à l'école.", "びょうきで、 がっこうへ いかなかった。", "아파서 학교에 안 갔어."),
        T("我們去 hospital 吧。", "We go to the hospital.", "Allons à l'hôpital.", "びょういんへ いこう。", "병원에 가자."),
        T("好。謝謝你。", "Ok. Thank you.", "Ok. Merci.", "いいよ。 ありがとう。", "그래. 고마워."),
    ],
    [
        T("你拿 medicine 了嗎？", "Did you take your medicine?", "As-tu pris ton médicament ?", "くすりを もった？", "약 가져왔어?"),
        T("拿了。醫生說一天吃 {n} 次。", "Yes. The doctor says to take it {n} times a day.", "Oui. Le médecin dit {n} fois par jour.", "のんだ。 いしゃは 1にちに {n}かいと いった。", "응. 의사가 하루에 {n}번 먹으래.", n=COUNTS),
        T("那你早一點睡。", "Then sleep early.", "Alors dors tôt.", "じゃ はやく ねて。", "그럼 일찍 자."),
    ],
    [
        T("你要多喝水，多睡。", "Drink more water and sleep more.", "Bois plus d'eau et dors plus.", "水を たくさん のんで、 たくさん ねて。", "물 많이 마시고 푹 자."),
        T("是。謝謝你。", "Yes. Thank you.", "Oui. Merci.", "うん。 ありがとう。", "그래. 고마워."),
    ],
]

OUTING_CHAINS = [
    [
        T("weekend 我們去{place}玩吧。", "We go to {place} on the weekend.", "Allons à {place} ce weekend.", "しゅうまつ {place}へ あそびに いこう。", "주말에 {place}에 놀러 가자.", place=PLACES),
        T("好。我要去看{t}。", "Ok. I want to see {t}.", "Ok. Je veux voir {t}.", "いいよ。 {t}が みたい。", "그래. 나는 {t} 보고 싶어.", t=THINGS_SEE),
        T("我拿{f}和{t2}去。", "I take {f} and {t2}.", "Je prends {f} et {t2}.", "{f}と {t2}を もって いく。", "나는 {f}랑 {t2} 가져갈게.", f=FOODS, t2=THINGS),
        T("好。早上 {h} 點見。", "Ok. See you at {h} in the morning.", "Ok. À {h} heures du matin.", "いいよ。 あさ {h}じに。", "그래. 아침 {h}시에 보자.", h=HOURS),
    ],
    [
        T("我們去海邊吧。", "We go to the sea.", "Allons à la mer.", "うみへ いこう。", "바다로 가자."),
        T("好。海很{col}。", "Ok. The sea is very {col}.", "Ok. La mer est très {col}.", "いいよ。 うみは とても {col}。", "그래. 바다가 아주 {col}야.", col=SEA_COLORS),
        T("我喜歡看海。", "I like to look at the sea.", "J'aime regarder la mer.", "うみを みるのが すきだ。", "나는 바다 보는 걸 좋아해."),
        T("我也是。下次再來。", "Me too. We come again next time.", "Moi aussi. On revient la prochaine fois.", "わたしも。 つぎも こよう。", "나도. 다음에 또 오자."),
    ],
    [
        T("明天你有空嗎？", "Are you free tomorrow?", "Es-tu libre demain ?", "あした ひま？", "내일 시간 있어?"),
        T("有。怎麼了？", "Yes. Why?", "Oui. Pourquoi ?", "あるよ。 どうした？", "있어. 왜?"),
        T("我們去打球吧。", "We go to play ball.", "On va jouer au ballon.", "ボールを あそびに いこう。", "공 하러 가자."),
        T("好。{h} 點在{place}見。", "Ok. See you at {place} at {h}.", "Ok. À {place} à {h} heures.", "いいよ。 {h}じに {place}で。", "그래. {h}시에 {place}에서 보자.", h=HOURS, place=PLACES),
    ],
]

PHONE_CHAINS = [
    [
        T("你在什麼地方？", "Where are you?", "Où es-tu ?", "いま どこ？", "지금 어디야?"),
        T("我在{place}。", "I am at {place}.", "Je suis à {place}.", "{place}に いる。", "{place}에 있어.", place=PLACES),
        T("我等你 {min} 分鐘了。", "I waited for you {min} minutes.", "Je t'attends depuis {min} minutes.", "{min}ぷん まって いた。", "{min}분 기다렸어.", min=MINDUR),
        T("對不起。我快來了。", "I am sorry. I come soon.", "Pardon. J'arrive.", "ごめん。 すぐ いく。", "미안. 금방 갈게."),
    ],
    [
        T("你的電話是多少？", "What is your phone number?", "Quel est ton numéro de téléphone ?", "でんわばんごうは？", "전화번호가 뭐야?"),
        T("{num}。", "It is {num}.", "C'est le {num}.", "{num}だよ。", "{num}이야.", num=PHONE_NUMS),
        T("好。我記下了。", "Ok. I write it down.", "Ok. Je le note.", "いいよ。 メモした。", "그래. 적어뒀어."),
    ],
]

THEMES = {
    "time": TIME_CHAINS,
    "weather": WEATHER_CHAINS,
    "food": FOOD_CHAINS,
    "shopping": SHOPPING_CHAINS,
    "transport": TRANSPORT_CHAINS,
    "school": SCHOOL_CHAINS,
    "family": FAMILY_CHAINS,
    "health": HEALTH_CHAINS,
    "outing": OUTING_CHAINS,
    "phone": PHONE_CHAINS,
}


# ---------------------------------------------------------------- 產生與檢查

def zh_charset():
    spec = SPEC.read_text(encoding="utf-8")
    seg = spec[spec.index("## 中文字集"):spec.index("## 日語")]
    return set(re.findall(r"[\u4e00-\u9fff]", seg))


def iter_template_texts(tpl):
    for lang in LANGS:
        yield lang, tpl[lang]
    for pool in tpl["slots"].values():
        for v in pool:
            for lang in LANGS:
                yield lang, v[lang]


def validate_templates(allowed):
    """中文行用字必須全在中文字集內；日文漢字、韓文漢字不符合只警告。"""
    problems = []
    warnings = []
    for theme, chains in THEMES.items():
        tpls = list(FILLERS) + [t for chain in chains for t in chain]
        for i, tpl in enumerate(tpls):
            for lang, text in iter_template_texts(tpl):
                for ch in text:
                    if not ("\u4e00" <= ch <= "\u9fff"):
                        continue
                    if lang == "中" and ch not in allowed:
                        problems.append(f"{theme} 模板{i} 中「{ch}」不在中文字集：{text}")
                    elif lang == "日" and ch not in allowed:
                        warnings.append(f"{theme} 模板{i} 日文漢字「{ch}」不在中文字集")
                    elif lang == "韓":
                        warnings.append(f"{theme} 模板{i} 韓文含漢字「{ch}」")
    return problems, warnings


def render_turn(tpl, spk, rng):
    vals = {k: rng.choice(pool) for k, pool in tpl["slots"].items()}
    lines = []
    for lang in LANGS:
        fmt_lang = {k: (v[lang] if isinstance(v, dict) else v) for k, v in vals.items()}
        text = tpl[lang].format(**fmt_lang)
        lines.append(f"{lang} {spk}: {text}")
    return "\n".join(lines)


def gen_dialogue(theme, rng):
    chain = rng.choice(THEMES[theme])
    turns = []
    for tpl in chain:
        turns.append(tpl)
        if rng.random() < 0.35:
            turns.append(rng.choice(FILLERS))
    rng.shuffle  # no-op; 對話保持鏈的順序
    parts = [f"# mini-x 合成多語對話：{theme}（由 llm/generate_corpus.py 產生）"]
    spk = "A"
    for tpl in turns:
        parts.append(render_turn(tpl, spk, rng))
        spk = "B" if spk == "A" else "A"
    return "\n\n".join(parts) + "\n"


def main(argv):
    ap = argparse.ArgumentParser(description="產生 mini-x 合成多語對話語料")
    ap.add_argument("--theme", choices=sorted(THEMES), help="只產生某個主題")
    ap.add_argument("--per-file", type=int, default=300, help="每個主題檔的對話篇數")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args(argv[1:])

    rng = random.Random(args.seed)
    problems, warnings = validate_templates(zh_charset())
    for w in sorted(set(warnings)):
        print(f"警告：{w}")
    if problems:
        for p in problems:
            print(f"錯誤：{p}")
        return 1

    GEN_DIR.mkdir(parents=True, exist_ok=True)
    themes = [args.theme] if args.theme else sorted(THEMES)
    total_turns = 0
    for theme in themes:
        chunks = []
        for _ in range(args.per_file):
            d = gen_dialogue(theme, rng)
            total_turns += d.count("中 A:") + d.count("中 B:")
            chunks.append(d)
        out = GEN_DIR / f"gen_{theme}.txt"
        out.write_text("\n\n".join(chunks), encoding="utf-8")
        print(f"{out.relative_to(ROOT.parent)}: {len(chunks)} 篇對話，{out.stat().st_size:,} bytes")
    print(f"完成：{len(themes)} 個主題檔，共 {total_turns:,} 個回合")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
