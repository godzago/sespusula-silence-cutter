# Mac güncel sürüm hazırlığı — 0.8.1

- Windows güncel kurgu çekirdeği ve koyu Bento tasarımı yeni Mac klasörüne taşındı.
- Önceki çalışan Mac paketinin ARM bağımlılıkları ve hash kilitleri korundu. Intel ve Windows paketleri eklenmedi.
- macOS 26+, yerel arm64 hedefi; M1–M5 ve Neo hedef cihazlar, bütün cihazlarda test yapıldığı iddia edilmez.
- Yeni uygulama adı SesPusula.app; ayrı bundle kimliği ve ayar klasörü eski SesPusulaMac uygulamasından ayrılır.
- Mac yazı tipi seçimi ve Retina bilgileri eklendi.
- Onaysız kesim, 100 ms pay, yalnızca işaretlenen tekrarlar, isteğe bağlı altyazı/SRT ve kaynak koruma güncel Windows sürümüyle aynıdır.
- Kaynak değiştiğinde kurulum doğrulaması yenilenir; arm64 Python ve kilitli çevrimdışı paketler kontrol edilir.
- Build sonrası gerçek .app içindeki Python ve bağımlılıkların kendi kendine yeterliliği kontrol edilir; ardından uygulama ZIP'i üretilir.
- Windows üzerinde yeni klasörün gerçek kodundan 71 test geçti; paket/model hashleri, bağımlılık grafiği ve bash sözdizimi doğrulandı.
- Yeni .app henüz Mac'te derlenmedi veya çalıştırılmadı. CapCut görünüm/render ve tüm cihaz matrisi doğrulanmadı.
