# SesPusula 0.8.1

- Analiz parçası sınırında kelimenin başının/sonunun kırpılması düzeltildi; kelime ana klibe göre sınırlandırılır. Eski ham model önbelleği korunur, çıktı işleme revizyonu yeni inceleme kimliği oluşturur.
- Çakışan kelime zamanlarında altyazının erken bitmesi düzeltildi.
- Tekrar altyazı üretiminde önceki otomatik altyazı katmanının çoğalması düzeltildi; diğer metinler ve ortak materyaller korunur. Yeni kesilmiş çıktıya eski zamanlı araç SRT'si taşınmaz.
- Aynı tekrar işaretlerinin çoğalması ve dışa aktarımda gereksiz tekrar analizi/model çağrıları önlendi. Boş tekrar sonucu da yeniden kullanılır.
- Kesim listesi ve altyazı imzası değişiklik revizyonuna göre önbelleğe alındı. 4.000 kesimde değişmeyen imzanın 200 kontrolü bu makinede yaklaşık 1,051 sn → 0,000263 sn; yalnızca bu küçük arayüz hesabıdır, toplam analiz/Whisper süresi değildir.
- Önbellek temizliğinde eşzamanlı dosya silinmesi toleransı eklendi. Proje klasörü dışına çıkan zaman çizelgesi kimlikleri reddedilir.
- 50 test geçti. Gerçek 20 sn ses, top5 kayıtlı 414 kesim/5 işaretle geçici kopya, kaynak hashleri, paket kendini testi ve native 0.8.1 açılışı doğrulandı. CapCut görünüm/dışa aktarımı doğrulanmadı.
- Yedek `.state/audit-backup-*` altında. Onaysız kesim, 100 ms pay, hazır hizalı katmanlar ve isteğe bağlı altyazı akışı korunur.

## 0.8.0 değişiklikleri

- Onay akışı kaldırıldı. Sessizlikler otomatik kesilir; dolgu/tekrar konuşmaları otomatik silinmez. Tekrarlar çıktı zaman çizelgesinde turuncu nokta işaretleri olur. Eski onay listesi yeni politikaya taşınmaz.
- Sessizliği sonraki konuşmadan 100 ms öncesine kadar kesme kuralı eklendi. Önceki otomatik tempo ve cümle duraklamaları kullanılmaz. Bir tam kare çıkarılabilen kısa boşluklar ve ana mikrofon klipleri arasındaki boşluklar da işlenir. 100 ms, belirsiz kullanıcı ifadesinden alınan açıkça belirtilmiş varsayımdır.
- Kesimlerden sonra altyazı eskirse kopya düğmesini kilitleyen koşul kaldırıldı. Kopyalama sırasında altyazı otomatik hazırlanır/yenilenir. Aynı kesimlerde elle metin düzeltmeleri korunur. Altyazı açmak da ayrı onay gerektirmez; düzenleyici isteğe bağlıdır.
- Kopya oluştur düğmesi analiz tamamlandığında onay beklemeden kullanılabilir. Kopyalama hataları ve uyumluluk sorunları açık hata mesajı verir; veri koruma kontrolleri korunur.
- Tekrarlar, eski işaretler ve altyazılar final kesim zamanına eşlenir. İşaret eşleme birikimli kesim süreleri ve ikili arama kullanır.
- 39 test başarılı. top5 projesinin kayıtlı eski kesim listesiyle geçici kopyada 414 kesim ve beş tekrar işareti doğrulandı; orijinal değişmedi. Bu test bütün projede yeni konuşma analizi yapıldığı anlamına gelmez. Yeni kural, 20 sn gerçek ses örneğinde altı kesim/yedi altyazı ve 11 sn çıktı üretti; JSON/SRT okundu. CapCut görünümü/dışa aktarımı henüz doğrulanmadı.
- Yedek `.state/direct-cut-backup-*` altında.

## 0.7.0 değişiklikleri

- Başlangıç/bitiş alanları kaldırıldı; uygulama daima bütün zaman çizelgesini işler. Eski aralık ve manuel kesim tercihleri otomatik profili değiştiremez.
- Kesim ayarları ve Hızlı mod yerine otomatik jump cut eklendi. Kısa duraklamalar korunur; uzun boşluklar konuşma ritmine göre seçilen 0,35–0,60 sn eşikle kısaltılır, konuşma arasında yaklaşık 0,20–0,28 sn pay hedeflenir.
- Metin analizi açıksa noktalama sonlarında daha uzun pay bırakılır. Baş/son ölü boşlukları konuşmaya bakan tarafta korunur; iki kareden veya 0,08 sn'den kısa kesimler elenir. Hiç konuşma bulunmazsa tüm kayıt silinmez.
- Sayısal profil yerel bir kurgu sezgisidir; araştırılan kaynaklar jump cut ve duraklama kısaltma mantığını açıklar, evrensel bir sayısal ayar vermez. Kaynaklar ve algoritma README.md içinde.
- Hazır hizalanmış katmanlar, mevcut ses seviyeleri, eşzamanlı kesim ve isteğe bağlı altyazı korunur. Otomatik senkron yoktur.
- 28 test başarılı. Gerçek sesle otomatik kesim + altyazı üretimi ve JSON/SRT okuması kontrol edildi. CapCut görünümü/dışa aktarımı henüz doğrulanmadı.
- Geri dönüş yedeği `.state/jump-cut-backup-*` altında.

## 0.6.2 değişiklikleri

- Kullanıcı senkron sonucunun işe yaramadığını bildirdi; otomatik/elle senkron özelliği, katman kaydırma, ortak aralığa kırpma ve ses seviyesi ayarlama kodu kaldırıldı. Senkronun başarısızlık nedeni ayrıca teşhis edilmiş değildir.
- Hazır hizalanmış CapCut projesi doğrudan kullanılır. Temiz mikrofon analiz kaynağı seçilir, sessizlikler bütün katmanlardan aynı aralıkta çıkarılır. Katmanların kaynak zamanları, mevcut baş/son kapsamı ve ses seviyeleri korunur.
- Senkron adımı ve tek klip şartı yoktur. Normal hızlı çok klipli katmanlar desteklenir; önceki genel uyumluluk kontrolleri korunur.
- İsteğe bağlı otomatik Türkçe altyazı, metin düzeltme ve SRT çıktısı korunur. Kesimler değişirse altyazı yenilenir.
- Güncel akış için 20 regresyon testi başarılı. Hazır hizalanmış üç katman, farklı klip kapsamı/kaynak başlangıcı, ses seviyelerini koruma, yalnızca ana mikrofondan analiz, çok klipli kesim ve altyazı zaman eşleme kontrol edildi. Önceki sürümlere ait senkron test raporları güncel sürüm özelliği değildir.
- Önceki sürümün geri dönüş yedeği `.state/remove-sync-backup-*` altında tutuldu.

## 0.6.1 değişiklikleri

- İsteğe bağlı otomatik Türkçe altyazı düğmesi ve Ekle kutusu eklendi. Ana mikrofon yerel Whisper ile çözümlenir; kesim kararları korunur.
- Kesilen kelimeler elenir; kalan kelimeler çıktı zamanına eşlenir. Her kesim birleşiminde ayrı altyazı başlar. Satırlar eklemeden önce düzeltilebilir.
- CapCut kopyasına beyaz, siyah kenarlıklı, alt ortada normal düzenlenebilir metin katmanı eklenir. Aynı klasöre otomatik_altyazi.srt yazılır. Sıfır kesimle de altyazılı kopya oluşturulabilir.
- Kesimler değişirse eski zamanlı altyazıyla kopyalama engellenir. Yenilemek elle metin düzeltmelerini yeniden oluşturur. Özellik tek kutuyla kapatılabilir; orijinal ve mevcut metin katmanları korunur.
- 25 test, taşınabilir kendini testi ve native EXE 0.6.1 açılışı başarılı. 20 saniyelik gerçek ses örneğinde 21 kelimeden 6 altyazı üretildi; JSON ve SRT yeniden okundu. CapCut içindeki görünüm ve dışa aktarım henüz doğrulanmadı.

## 0.6.0 değişiklikleri

- Ana mikrofon, webcam ve ekran kaydı için ayrı seçim ve çok pencereli yerel ses eşleştirme eklendi. Güvenilir olmayan eşleşmeler ve zamanla değişen gecikmeler otomatik uygulanmaz. Her seçili katmanda tek sürekli kayıt gerekir.
- Kaydırmaları elle düzenleme, ayrı kaynakları hizalanmış şekilde dinleme ve çıktıdaki ortak aralığı kontrol etme ekranı eklendi. Ortak olmayan baş/son kopyada çıkarılır. Otomatik hız/clock drift düzeltmesi yapılmaz.
- Webcam sessiz, ana mikrofon %100, ekran/oyun ayarlanabilir (varsayılan −18 dB). Ekranın karışık sesindeki konuşma da oyunla birlikte kısılır.
- Boşluklar ana mikrofondan bulunur; bütün katmanlardan birlikte kesilir. Analizsiz senkron/ses kopyası da oluşturulabilir. İnceleme kararlarının kimliğine senkron ayarları eklendi.
- Kelime başı ve sonu ayrı korunur; tam kareye yuvarlandıktan sonra çok kısa kesimler elenir. Kaydedilmiş eski koruma payı korunur.
- Kesim uygulaması yalnızca kliple çakışan kesimleri tarar; zaman eşlemesinde birikimli süreler ve ikili arama kullanır. 4.000 kesim/3 katman sentetik testinde eski ve yeni zaman çizelgeleri aynı: yaklaşık 21,37 sn → 0,163 sn. Bu ölçüm Whisper/VAD hızını ifade etmez.
- Güncelleme regresyonları ve taşınabilir paket kendini testi çalıştırıldı. İşlenmiş gerçek ses örneğinde eklenen 1,73 sn gecikme doğru bulundu. Gerçek üç cihaz kaydı ve CapCut dışa aktarımı henüz doğrulanmadı. Windows arayüzü kontrol edildi; macOS çalıştırılmadı.
- Güncelleme öncesi kaynak dosyalar .state/update-backup-* altında saklandı. Bunlar dağıtım paketine eklenmemelidir.
## 0.5.2 değişiklikleri

- Türkçe önerilerde her kelime bir kez normalize edilir; yinelenen öneri ve kapsama kontrolleri yalnızca ilgili zaman aralığını tarar. Eski sürümle 201 karşılaştırmada sonuçlar aynı kaldı. 3.500 kelimelik örnekte öneri hesaplama yaklaşık 4,5 kat hızlandı; bu oran Whisper çözümleme hızını ifade etmez.
- Ayarlar ve analiz seçenekleri tek dosya yazımıyla kaydedilir. Arayüzde tüm widget ağacını tekrar tekrar tarama ve kesim tablosunda gereksiz satır sorguları kaldırıldı.
- Windows çalışma paketinden Python'un kendi testleri, IDLE/demolar, paket kurulum araçları ve kullanılmayan model dönüştürme araçları çıkarıldı. Uygulama testleri geliştirme/Mac kaynak paketinde korunur.
- Mac'te Windows'a özgü gereksiz dört paket çıkarıldı. İki mimarinin aynı olan 23 Python paketi `wheelhouse/common` altında bir kez tutulur. Native paketler mimariye göre ayrıdır; hash kilitleri güncellendi.
- Mac kaynak başlatıcısı başarılı kurulumdan sonra paket kurulumunu ve ağır model testini her açılışta tekrarlamaz. Lock/manifest, konum veya Python sürümü değişirse yeniden doğrular. `setup_mac.py --verify` ve `Test Et.command` tam kontrolleri çalıştırır.
- `freeze_support`, minimum/maksimum sessizlik aralığı, manuel metin kesimleri, yerel karar kaydı ve kaldırma aracı korunur.

Bu sürümün temiz paketleri yeni bir klasöre çıkarılabilir. Eski bir Mac kaynak klasörünün üzerine yalnızca Python dosyalarını kopyalamak, ortak wheel düzenine geçişi tamamlamaz; `wheelhouse` ve kilit dosyaları da yeni paketten gelmelidir. Derlenmiş Mac uygulaması Mac üzerinde yeniden oluşturulmalıdır. Native macOS doğrulaması burada yapılmadı.

## 0.5.1 değişiklikleri

- Mac `draft_info.json` projeleri açılır; düzenlenmiş kopya aynı dosya adıyla yazılır.
- PyInstaller uygulamalarında multiprocessing yardımcıları arayüzden önce yönlendirilir. Metin çıkarırken `-B` parametresinin proje klasörü sanılması önlenir.
- Ayarlardaki **En kısa boşluk** ve **En uzun** alanları her iki analiz modunda kullanılır. Örnek: `0,2` ve `0,8` değerleri 0,2–0,8 saniye arasındaki sessizlikleri seçer; daha uzun boşlukları korur. Sınırlar dahildir; maksimum boşsa üst sınır yoktur. Karşılaştırma konuşma payı ve kare yuvarlamasından önce yapılır. İki yandaki konuşma payı kısa boşluğun tamamını kaplıyorsa kesim oluşmaz; 0,2 saniyelik boşluk için varsayılan iki adet 0,1 saniye pay bunu yapabilir. Payı dinleyerek ayarlayın.
- Başlangıç/bitiş alanları videonun analiz edilecek bölümünü seçmeye devam eder.
- `Programi Sil.py` seçilen kurulumun program dosyalarını, modelini ve yerel ayarlarını onayla kaldırır. Windows'ta `Programi Sil.cmd`, Mac'te `Programi Sil.command` çalıştırılır. Mac başlatıcısı kişisel uygulama ayarlarını da kapsar. Önce SesPusula'yı kapatın. CapCut projeleri ve kaynak medyalar silinmez; kurulum klasöründeki liste dışı öğeler korunur. Başka yere kopyaladığınız `.app` veya diğer SesPusula kurulumları ayrıca kaldırılmalıdır.
- `Programi Sil.py --list` silinecek öğeleri hiçbir şey silmeden gösterir. Tek kurulum seçilir; komşu SesPusula klasörleri otomatik silinmez.

## Mevcut kurulumu güncelleme

Güncelleme ZIP'inin içindekileri mevcut SesPusulaMac veya SesPusulaPortable klasörüne çıkarıp dosyaları değiştirin. `.models`, `.venv`, `.runtime` ve `wheelhouse` klasörlerini koruyun.

Mac: `Mac Uygulamasini Olustur.command` ile yeniden derleyip `Dagitim` altındaki yeni `.app` dosyasını açın. Kaynaktan çalıştırmak için `Kur ve Ac.command` kullanılır. Yalnızca kaynak dosyalarını değiştirmek, daha önce derlenmiş `.app` içeriğini değiştirmez. Derleme sonundaki kendini test etme adımı artık süreç başlatma ve Whisper metin çözümleme hattını da denetler.

Windows: Güncellenmiş SesPusulaPortable klasöründeki `SesPusula.exe` ile açın.

Windows testleri ve gönderilen Mac JSON projesi üzerinde yapısal kopyalama burada doğrulanabilir. Gerçek macOS çalışması ve CapCut Mac'te çıktıyı açma ayrıca Mac üzerinde doğrulanmalıdır.


