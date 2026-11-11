# SesPusula 0.8.1

CapCut projelerindeki sessizlikleri bulur; orijinali koruyarak düzenlenebilir bir kopya oluşturur. Türkçe altyazı, olası tekrarları zaman çizelgesinde işaretleme ve metinden elle bölüm çıkarma seçenekleri vardır. Sessizlik kesimi onay beklemez. Normal kullanım tamamen yereldir.

## Hazır hizalanmış üç katmanla kullanım

Webcam, ekran/oyun ve temiz mikrofonu CapCut'ta kendiniz hizalayın. Ses seviyelerini de CapCut'ta ayarlayıp projeyi kaydedin. SesPusula artık kayıt eşleştirmez, katman kaydırmaz veya ses seviyelerini değiştirmez. Ortak aralık bahanesiyle baş/son kırpması yapmaz; yalnızca seçtiğiniz kesimler uygulanır.

1. Hazır hizalanmış CapCut projesini açın.
2. **Ana mikrofon / sessizlik analiz kaynağı** alanından 3. katmandaki temiz sesi seçin. Katman numarasını ve dosya adını kontrol edin; oyun veya webcam sesini analiz kaynağı yapmayın.
3. **Jump cut analiz et** ile analiz edin, kesim sınırlarını dinleyerek kontrol edin. Seçilen sessizlikler bütün katmanlardan aynı zaman aralığında çıkarılır. Katmanların önceden ayarlanmış kaynak zamanları ve ses seviyeleri korunur. Kaynak katmanda birden fazla normal hızlı klip bulunabilir.
4. İsterseniz **Otomatik altyazı** ile altyazıyı açın. Ayrı onay gerekmez; metin düzenleme isteğe bağlıdır.
5. CapCut'ı kaydedip kapatın, **CapCut kopyası oluştur** düğmesine basın. Orijinal korunur, kesilmiş ve isteğe bağlı altyazılı yeni proje hazırlanır.

Uygulama hizalamanın doğruluğunu kontrol etmez; verilen zaman çizelgesini esas alır. `sessizlik_raporu.json` uygulanan kesimleri ve varsa altyazıları içerir. Gelişmiş efekt/geçiş/bağlı klip uyumluluk kısıtları sürer.

## Otomatik Türkçe altyazı ve tekrar işaretleri

- **Otomatik altyazı** düğmesi veya **Ekle** kutusu altyazıyı açar. Hazırlanan satırlar otomatik kaydedilir ve kopyaya eklenir; ayrı onay penceresi gerekmez. Hazır olduğunda aynı düğmeye tekrar basmak isteğe bağlı metin düzenleyicisini açar.
- Metin yerel Whisper ile ana mikrofonun tamamından çıkarılır. İlk çözümleme uzun sürebilir; uygun ses/model önbelleği ve mevcut metin yeniden kullanılır.
- Kesilen kelimeler çıkarılır; kalan kelimeler çıktı zamanına eşlenir. En fazla iki satır; yatayda satır başına 42, dikeyde 28 karakter hedeflenir. Metinler beyaz, siyah kenarlıklı, alt ortada normal düzenlenebilir CapCut metin klipleri olur.
- Kesimleri sonradan değiştirirseniz **kopya oluşturma kapanmaz**. Altyazı zamanları kopyalama sırasında son kesimlere göre otomatik yenilenir. Değişen kesimlerde satırlar yeniden oluşturulduğundan elle yapılmış metin düzeltmeleri yeniden yapılabilir; kesimler değişmediyse metin düzeltmeleri korunur.
- **Ekle** kutusunu kapatırsanız yeni kopyaya altyazı eklenmez. Çıktıda ayrıca `otomatik_altyazi.srt` bulunur.
- **Tekrarları işaretle** varsayılan açıktır. Benzer veya art arda yinelenen konuşmalar metinden bulunur; uygun iki tekrar konumuna turuncu **Tekrar olabilir** zaman işaretleri eklenir. Tekrarlar otomatik silinmez ve hiçbir işaret onay beklemez. Bu seçenek açıksa metin çıkarma da çalışır.
- Tekrar işaretleri son kesimlere göre yeniden zamanlanır. Önceden var olan desteklenen işaretler korunur ve taşınır; tamamen kesilmiş içerikteki işaretler çıkarılır. İşaret şeması teknik referansı: https://github.com/chuk-development/chukcut/blob/master/docs/research/draft-format.md .

Konuşma tanıma ve tekrar benzerliği hata yapabilir; işaretler kesin tekrar tespiti iddiası değildir. JSON/SRT ve zaman işaretleri test edildi; CapCut içindeki görünüm ve dışa aktarım henüz doğrulanmadı.

## 0.8.1 hata düzeltmeleri ve performans

- Beş dakikalık analiz parçalarının sınırına denk gelen kelimeler artık parça sınırında kırpılmaz; ana klibin içindeki tam kelime zamanı korunur. Sözcük zamanları çakıştığında altyazı erken bitmez.
- Yeni altyazı üretilirken yalnızca adı tam olarak `SesPusula · Otomatik altyazı` olan eski otomatik metin katmanı yenilenir. Kullanıcının diğer metin katmanları ve ortak kullanılan materyalleri korunur. Kesim yapılmış fakat yeni altyazı üretilmemiş kopyada eski zamanları taşıyan `otomatik_altyazi.srt` dosyası çıkarılır; orijinal dosyaya dokunulmaz.
- Aynı konum/başlıktaki tekrar işaretleri kopyayı yeniden işlerken çoğalmaz.
- Daha önce hesaplanmış tekrar sonucu dışa aktarımda yeniden hesaplanmaz; sıfır tekrar bulunan sonuç da geçerli bir sonuçtur.
- Değişmeyen kesim listesi ve altyazı geçerlilik imzası arayüzde önbelleğe alınır. Kesim değişince, düzenlenince veya kayıt geri yüklenince bu önbellek yenilenir. Bu işlem arayüz hesaplamasını azaltır; Whisper/VAD modelinin hızının arttığı anlamına gelmez.
- Önbellek temizliği başka uygulama örneğinin sildiği dosya yüzünden başarılı analizi hataya düşürmez. Geçersiz ve klasör dışına çıkan zaman çizelgesi kimlikleri reddedilir.

50 test, gerçek ses çözümlemesi, top5 kayıtlı kesimlerinin geçici kopyası, paket kendini testi ve 0.8.1 başlatıcı açılışı başarılı. CapCut içindeki görünüm/dışa aktarım bu kontrollerle doğrulanmış sayılmaz. Ayrıntılar `Dogrulama/update-v0.8.1.json` içinde.

## Başlatma

- Windows taşınabilir paket: `SesPusula.exe`. Ayrı Python kurulumu gerekmez; klasörün tamamını taşıyın.
- Mac kaynak paketi: Tk içeren Python 3.11 ve macOS 13 veya üstü gerekir. `Kur ve Ac.command` ilk kurulumu yerel paketlerden yapar. Sonraki açılışlarda doğrulanmış ortam kullanılır.
- Mac uygulaması: `Mac Uygulamasini Olustur.command` ile Mac üzerinde derleyin. `Dagitim/<mimari>/SesPusulaMac.app` aynı mimarideki uyumlu Mac'e taşınabilir. Windows üzerinde native Mac uygulaması derlenmez.

## Kullanım — onaysız kesim

1. Hazır hizalanmış projeyi açıp temiz mikrofonu seçin.
2. **Jump cut analiz et** düğmesine basın. Ana sesteki sessizlikler doğrudan kesime dahil edilir; onay listesi yoktur. Tekrarlar yalnızca işarettir; dolgu sözcükleri otomatik silinmez.
3. İsterseniz herhangi bir kesimi dinleyip **Bu aralığı koru** ile geri alın veya **Aralığı düzelt** ile sınırını değiştirin. Bu kontroller isteğe bağlıdır; kopya almak için kullanılmaları gerekmez.
4. İsterseniz altyazıyı açın.
5. CapCut'ı kaydedip kapatın ve **CapCut kopyası oluştur** düğmesine basın. Yeni kopya üretilir, orijinal korunur. Altyazı eskimişse kendisi yenilenir. Desteklenmeyen yapılar veya başka bir hata varsa neden gösterilir; sırf onay eksikliği yüzünden düğme kilitlenmez.

Kesim yoksa da kopya oluşturulabilir. Kaynak medyaları taşımayın; çıktı bu dosyalara başvurur. Yeni kesim politikası eski dolgu/tekrar onaylarını yeniden kullanmaz; güncel analiz otomatik kesim ve yalnızca tekrar işaretleriyle başlar.

## Sessizlik kuralı — sonraki konuşmadan önce 100 ms

Kullanıcının `0.1ms saniye` ifadesi **0,1 saniye = 100 ms** olarak yorumlandı; birim sorusuna açık yanıt alınmadan bu varsayımla ilerlenildi. 0,1 milisaniye ile aynı değildir.

Ana ses konuşmasının bittiği yerden sonraki konuşmanın 100 ms öncesine kadar sessizlik kesilir. Önceki 0,20–0,28 sn tempo/cümle duraklaması profili bu akışta kullanılmaz. Kayıt başındaki sessizlik ilk konuşmanın 100 ms öncesine kadar, sondaki sessizlik kayıt sonuna kadar kesilir. Ana mikrofon katmanında klip bulunmayan aralıklar da sessizdir. Yalnızca en az bir tam video karesi çıkarılabiliyorsa kesim oluşur.

Kesimler tam kareye **içeri** yuvarlanır: konuşma korunur; kalan gerçek pay hedeflenen 100 ms'den bir kareye kadar daha uzun olabilir. Hiç konuşma bulunmazsa bütün kayıt otomatik silinmez. Konuşma sınırları VAD ve varsa kelime zamanlarıyla tahmin edilir; algısal doğruluk garanti edilmez.

Üç katman aynı kesim zamanlarıyla düzenlenir. Önceden yapılmış hizalama ve ses seviyeleri korunur. Otomatik senkron, zoom veya geçiş eklenmez.

## Yerel analiz ve veri

Silero VAD konuşmayı, Whisper small CPU/int8 Türkçe metni işler. Konuşma sırasında duyulan klavyeyi sesin içinden ayırmaz; konuşma olmayan klavyeli aralıkları çıkarabilir. Hiç konuşma bulunmazsa kaydın tamamı otomatik silinmez.

Ses beş dakikalık bağlamlı parçalar halinde işlenir. Hazırlanan ses ve analiz sonuçları kaynak/model/ortam revizyonuna göre önbelleğe alınır. Metin seçeneğini değiştirmek aynı sesi yeniden hazırlamaz. Aracın kendi önbelleği 512 MiB hedefine temizlenir; modeller bu sınırın dışındadır. İptal, araca ait analiz alt süreçlerini durdurur.

Ayarlar ve kararlar kaynak/Windows pakette `.state` altında, derlenmiş Mac uygulamasında `~/Library/Application Support/SesPusulaMac` içindedir. Kişisel kararlar ve videolar dağıtım ZIP'lerine eklenmez. Çıktının `sessizlik_raporu.json` dosyası kesimleri içerir.

## Uyumluluk

JSON sürümü **360000** ve tek zaman çizelgesi desteklenir. Windows CapCut 9.6.0.4097 ile çalışıldı; gönderilen Mac CapCut 9.5.0 projesinin JSON yapısı okuma/kopyalama testlerinde kullanıldı. Gerçek macOS çalışması ve CapCut Mac'te çıktıyı açma bu Windows ortamında doğrulanamaz.

Normal hızdaki video/ses, sabit görsel ve basit metin katmanları eşzamanlı kırpılır. Hız rampası, ters oynatma, birleşik klip, anahtar kare, geçiş, kelime zamanlamalı altyazı ve doğrulanmamış efektler çıktıyı engeller. Çok katmanlı eşleme otomatik testlerle kontrol edilir; gerçek çok katmanlı CapCut dışa aktarımını ayrıca kontrol edin.

## Kontrol ve kaldırma

Windows: `Kendini Test Et.cmd`. Mac kaynak: `Test Et.command`. Mac derlemesi, oluşan `.app` üzerinde ayrıca süreç başlatma, model, çözümleme ve arayüz kontrolü yapar. Kaynak kurulumu yeniden doğrulamak için `.venv/bin/python3 setup_mac.py --verify` kullanın.

`Programi Sil.py` yalnızca seçili SesPusula kurulumunun bilinen program dosyalarını kaldırır; önce listeyi gösterip onay ister. Windows'ta `Programi Sil.cmd`, Mac'te `Programi Sil.command` ile açılır. Kaynak ses/videolar, CapCut projeleri ve liste dışındaki öğeler korunur. Başka yere kopyalanmış uygulamalar ayrıca kaldırılır.

## Geliştirme

Bu çalışma klasörü taşınabilir Windows paketidir; önceki ana kaynak deposunun derleme betikleri burada bulunmaz. Sürümler `requirements-lock.txt` dosyasındadır. Güncel otomatik jump cut, kesim, altyazı, kopyalama ve arayüz regresyon testleri `tests` altındadır:

```text
.runtime\python.exe -m unittest discover -s tests -v
```

Aşağıdaki derleme komutları yalnızca tam ana kaynak deposunda kullanılabilir:

```text
python -m unittest discover -s tests -v
python build_windows_portable.py --output YENI_KLASOR
python prepare_mac_project.py --output YENI_MAC_KLASORU
```

Mac'in ortak Python paketleri `wheelhouse/common`, native paketleri `wheelhouse/arm64` ve `wheelhouse/x86_64` altında tutulur. Her mimarinin hash kilidi ve manifesti gereken tüm paketleri kapsar. Derleme araçları, lisanslar ve gerekli modeller korunur. Optimizasyon ölçümleri ana kaynak `.test-output/optimization-benchmark.json` dosyasındadır.

Bileşenler ve lisanslar: `Lisanslar`, paket metadata klasörleri ve `.models/whisper-small/local-manifest.json`. Model revizyonu `536b0662742c02347bc0e980a01041f333bce120`.


