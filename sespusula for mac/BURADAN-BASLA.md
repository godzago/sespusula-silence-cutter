# SesPusula — Mac'te başlatma

Bu klasör güncel tasarım ve özelliklerle hazırlanmış **Mac uygulaması oluşturma paketidir**. Henüz derlenmiş `.app` değildir; son adım Mac üzerinde yapılır.

## Bir kez yapacağın işlem

1. Masaüstündeki `SesPusula-macOS26-arm64-kaynak.zip` dosyasını Mac'e gönder ve aç.
2. Önceki çalışan sürüm için kurduğun Tk içeren Python 3.11 hâlâ varsa tekrar kurman gerekmez. Yoksa python.org üzerinden macOS universal2 Python 3.11 kur.
3. **Mac Uygulamasini Olustur.command** dosyasına çift tıkla.
4. İşlem bitince Finder'da **Dagitim → arm64 → SesPusula.app** seçilir.
5. `.app` dosyasını Uygulamalar klasörüne taşı. Sonraki kullanımlarda yalnızca bu uygulamayı aç; Python ve Terminal gerekmez.

Komut dosyası Finder'da açılmazsa Terminal'e `bash ` yaz, dosyayı pencereye sürükle ve Enter'a bas. Hata olursa `.build/son-islem.log` dosyası ayrıntıları tutar.

Oluşturulan uygulama eski **SesPusulaMac.app** ile farklı isim ve ayar klasörü kullanır. Eski sürümü silmez veya otomatik güncellemez.

## İlk kontrol

- Yeni koyu kart tasarımının ve süre göstergelerinin göründüğünü kontrol et.
- Kısa bir CapCut projesinde mikrofonu seçip analiz et.
- Bir kesimi dinle, koru, tekrar kesime dahil et; süre kartlarını kontrol et.
- Altyazıyı aç, CapCut'ı kaydedip kapat ve proje kopyası oluştur.
- Kopyayı CapCut'ta aç. Ses/görüntü hizasını, kesim sınırlarını, altyazıyı ve varsa tekrar işaretlerini kontrol et.
- Kısa bir video dışa aktar. Asıl kullanım doğrulaması budur.

Hedef macOS 26 ve Apple Silicon arm64'tür; M1–M5 ile Neo için ayrı ayrı paket gerekmez. Bu yeni sürümün bütün cihazlarda çalıştığı henüz doğrulanmadı. Windows'ta hazırlanan testler Mac'te gerçek çalıştırmanın yerini tutmaz.

İşlem sırasında internet gerekmez; modeller ve Mac bağımlılıkları pakettedir. Genel dağıtım için Apple Developer ID imzası/noter onayı eklenmedi; kendi Mac'inde oluşturulan uygulama yerel imza kullanır.

Detaylı ilk test listesi: [MAC-TEST.md](MAC-TEST.md).
