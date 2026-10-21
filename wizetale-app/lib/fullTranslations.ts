import type { Language } from "./i18n"

// COMPLETE translations map copied from former Fibonacci landing page project.
// If you update any keys, keep types in sync.

const translations: Record<Exclude<Language, 'kk'>, Record<string, string>> = {
  en: {
    // Header
    features: "Features",
    pricing: "Pricing",
    howItWorks: "How it Works",
    stories: "Stories",
    signIn: "Sign In",
    // Hero
    heroBadge: "Making Learning Magical",
    heroTitle1: "Learn History as a",
    heroTitle2: "Fairy Tale",
    heroSubtitle:
      "Transform complex humanities topics into engaging audio-visual stories. Make learning fun, memorable, and magical for students aged 10-18.",
    heroButton1: "Start Learning Now",
    heroButton2: "Watch Demo",
    heroVideoTitle: "See Fibonacci in Action",
    heroVideoSubtitle:
      "Watch how we transform complex history topics into engaging fairy tale stories",
    // How it works
    hiwTitle: "Learning Made Simple",
    hiwSubtitle:
      "Transform any humanities topic into an engaging story in just three easy steps",
    hiwStep1Title: "1. Choose Topic",
    hiwStep1Desc:
      "Select any humanities subject - history, philosophy, geography, or literature",
    hiwStep2Title: "2. Let AI Narrate",
    hiwStep2Desc:
      "Our AI transforms complex topics into engaging, easy-to-understand fairy tales",
    hiwStep3Title: "3. Watch & Listen",
    hiwStep3Desc:
      "Enjoy beautiful animations with professional voiceover and interactive quizzes",
    // Features
    featuresTitle: "Magical Learning Features",
    featuresSubtitle:
      "Everything you need to make humanities education engaging and memorable",
    feature1Title: "Professional Voiceover",
    feature1Desc:
      "High-quality AI narration brings stories to life with engaging character voices",
    feature2Title: "Story-Style Learning",
    feature2Desc:
      "Complex topics explained through memorable narratives and characters",
    feature3Title: "Interactive Quizzes",
    feature3Desc:
      "Test understanding with fun quizzes that reinforce key concepts",
    feature4Title: "Perfect Length",
    feature4Desc:
      "3-5 minute stories designed for optimal attention spans and retention",
    feature5Title: "Multi-Age Appeal",
    feature5Desc: "Content that engages students, parents, and teachers alike",
    feature6Title: "Curriculum Aligned",
    feature6Desc:
      "Stories designed to complement school curricula and learning objectives",
    // Pricing
    pricingTitle: "Choose Your Learning Adventure",
    pricingSubtitle:
      "Start free and unlock unlimited magical learning experiences",
    pricingFreeTitle: "Free Explorer",
    pricingFreePrice: "$0",
    pricingFreeDesc: "Perfect for trying out Fibonacci",
    pricingFreeFeature1: "3 stories per month",
    pricingFreeFeature2: "Basic history & geography",
    pricingFreeFeature3: "Standard quality audio",
    pricingFreeFeature4: "Simple quizzes",
    pricingFreeFeature5: "Mobile & web access",
    pricingFreeButton: "Start Free",
    pricingPremiumTitle: "Premium Access",
    pricingPremiumPrice: "$19.99",
    pricingPremiumDesc: "Lifetime access to all features",
    pricingPremiumFeature1: "Unlimited stories",
    pricingPremiumFeature2: "All subjects & topics",
    pricingPremiumFeature3: "Premium HD audio & visuals",
    pricingPremiumFeature4: "Interactive quizzes & games",
    pricingPremiumFeature5: "Progress tracking",
    pricingPremiumFeature6: "Offline downloads",
    pricingPremiumFeature7: "Priority support",
    pricingPremiumButton: "Buy Premium",
    pricingDiscountBadge: "New User Discount",
    pricingDiscountText: "Limited time offer for new users",
    pricingOriginalPrice: "$29.99",
    pricingFamilyTitle: "Family Adventure",
    pricingFamilyPrice: "$19.99",
    pricingFamilyDesc: "Perfect for families & homeschooling",
    pricingFamilyFeature1: "Everything in Premium",
    pricingFamilyFeature2: "Up to 6 family profiles",
    pricingFamilyFeature3: "Parental controls & reports",
    pricingFamilyFeature4: "Age-appropriate content",
    pricingFamilyFeature5: "Family learning goals",
    pricingFamilyFeature6: "Homeschool curriculum guide",
    pricingFamilyFeature7: "Priority family support",
    pricingFamilyButton: "Start Family Trial",
    pricingMoneyBack: "All plans include our 30-day money-back guarantee",
    pricingGuarantee1: "Cancel anytime",
    pricingGuarantee2: "No setup fees",
    pricingGuarantee3: "Secure payments",
    pricingEducatorsTitle: "Educators & Schools",
    pricingEducatorsDesc:
      "Special pricing for teachers and educational institutions",
    pricingEducatorsButton: "Get Educator Discount",
    pricingPopularBadge: "Most Popular",
    // Testimonials
    testimonialsTitle: "Stories That Inspire",
    testimonialsSubtitle:
      "See how Fibonacci transforms learning experiences for students and educators",
    testimonial1Name: "Ms. Sarah Johnson",
    testimonial1Role: "8th Grade History Teacher",
    testimonial1Quote:
      "My students are actually excited about history class now! The Roman Empire story had them completely engaged.",
    testimonial2Name: "Dr. Robert Chen",
    testimonial2Role: "Philosophy Professor",
    testimonial2Quote:
      "Finally, a way to make philosophy accessible to teenagers. The Socrates story was brilliant!",
    testimonial3Name: "Lisa Martinez",
    testimonial3Role: "Parent of 7th Grader",
    testimonial3Quote:
      "My daughter went from hating geography to asking for more stories about different countries!",
    // CTA
    ctaTitle: "Ready to Transform Learning?",
    ctaSubtitle:
      "Join thousands of educators and students who are making learning magical with Fibonacci",
    ctaInputPlaceholder: "Enter your email address",
    ctaButton: "Join Waitlist",
    ctaDisclaimer: "Get early access and exclusive updates. No spam, ever.",
    // Footer
    footerSlogan:
      "Making humanities education magical through AI-powered storytelling.",
    footerProductTitle: "Product",
    footerProductLink1: "Features",
    footerProductLink2: "How it Works",
    footerProductLink3: "Pricing",
    footerProductLink4: "Stories",
    footerEducatorsTitle: "For Educators",
    footerEducatorsLink1: "Classroom Tools",
    footerEducatorsLink2: "Curriculum Guide",
    footerEducatorsLink3: "Teacher Resources",
    footerEducatorsLink4: "Professional Development",
    footerSupportTitle: "Support",
    footerSupportLink1: "Help Center",
    footerSupportLink2: "Contact Us",
    footerSupportLink3: "Privacy Policy",
    footerSupportLink4: "Terms of Service",
    footerCopyright: "© 2025 Fibonacci. All rights reserved. Made with ❤️ for learners everywhere.",
    // Register Page
    registerTitle: "Create an account",
    registerSubtitle: "Enter your details to get started with Fibonacci",
    registerEmailLabel: "Email",
    registerEmailPlaceholder: "john@example.com",
    registerPasswordLabel: "Password",
    registerButton: "Create account",
    registerLoginPrompt: "Already have an account?",
    registerLoginLink: "Sign in",
    registerUsernameLabel: "Username",
    registerUsernamePlaceholder: "johndoe",
    registerDisplayNameLabel: "Display Name (optional)",
    registerDisplayNamePlaceholder: "John Doe",
    registerConfirmPasswordLabel: "Confirm Password",
    registerGoogleButton: "Sign up with Google",
    registerCreatingAccount: "Creating account...",
    // Login Page
    loginTitle: "Welcome back",
    loginSubtitle: "Enter your credentials to access your account",
    loginButton: "Sign in",
    loginRegisterPrompt: "Don't have an account?",
    loginRegisterLink: "Sign up",
    loginEmailLabel: "Email",
    loginEmailPlaceholder: "john@example.com",
    loginPasswordLabel: "Password",
    loginForgotPassword: "Forgot password?",
    loginGoogleButton: "Sign in with Google",
    loginSigningIn: "Signing in...",
    // Feedback Form
    feedbackEmailPlaceholder: "Email (optional)",
    feedbackMessagePlaceholder: "Your feedback, ideas or bugs...",
    feedbackSending: "Sending...",
    feedbackThankYou: "Thank you!",
    feedbackSendButton: "Send Feedback",
    feedbackError: "Failed to send. Please try again later.",
    orContinueWith: "Or continue with",
  },
  ru: {
    // Header
    features: "Возможности",
    pricing: "Цены",
    howItWorks: "Как это работает",
    stories: "Истории",
    signIn: "Войти",
    // Hero
    heroBadge: "Делаем обучение волшебным",
    heroTitle1: "Изучайте историю как",
    heroTitle2: "Сказку",
    heroSubtitle:
      "Превращаем сложные гуманитарные темы в увлекательные аудиовизуальные истории. Сделайте обучение веселым, запоминающимся и волшебным для учеников 10-18 лет.",
    heroButton1: "Начать обучение",
    heroButton2: "Смотреть демо",
    heroVideoTitle: "Посмотрите Fibonacci в действии",
    heroVideoSubtitle:
      "Узнайте, как мы превращаем сложные исторические темы в увлекательные сказочные истории",
    // How it works
    hiwTitle: "Обучение — это просто",
    hiwSubtitle:
      "Превратите любую гуманитарную тему в увлекательную историю за три простых шага",
    hiwStep1Title: "1. Выберите тему",
    hiwStep1Desc:
      "Выберите любой гуманитарный предмет — историю, философию, географию или литературу",
    hiwStep2Title: "2. Позвольте ИИ рассказать",
    hiwStep2Desc:
      "Наш ИИ превращает сложные темы в увлекательные и понятные сказки",
    hiwStep3Title: "3. Смотрите и слушайте",
    hiwStep3Desc:
      "Наслаждайтесь красивой анимацией с профессиональной озвучкой и интерактивными тестами",
    // Features
    featuresTitle: "Волшебные возможности обучения",
    featuresSubtitle:
      "Все, что нужно, чтобы сделать гуманитарное образование увлекательным и запоминающимся",
    feature1Title: "Профессиональная озвучка",
    feature1Desc:
      "Качественная озвучка от ИИ оживляет истории с помощью увлекательных голосов персонажей",
    feature2Title: "Обучение в стиле историй",
    feature2Desc:
      "Сложные темы объясняются через запоминающиеся повествования и персонажей",
    feature3Title: "Интерактивные тесты",
    feature3Desc:
      "Проверяйте понимание с помощью веселых тестов, которые закрепляют ключевые понятия",
    feature4Title: "Идеальная длина",
    feature4Desc:
      "3-5-минутные истории, разработанные для оптимальной концентрации внимания и запоминания",
    feature5Title: "Для всех возрастов",
    feature5Desc: "Контент, который увлекает учеников, родителей и учителей",
    feature6Title: "Соответствие учебной программе",
    feature6Desc:
      "Истории, разработанные для дополнения школьных программ и учебных целей",
    // Pricing
    pricingTitle: "Выберите свое учебное приключение",
    pricingSubtitle:
      "Начните бесплатно и откройте безграничные возможности для волшебного обучения",
    pricingFreeTitle: "Бесплатный исследователь",
    pricingFreePrice: "0₽",
    pricingFreeDesc: "Идеально, чтобы попробовать Fibonacci",
    pricingFreeFeature1: "3 истории в месяц",
    pricingFreeFeature2: "Базовая история и география",
    pricingFreeFeature3: "Стандартное качество аудио",
    pricingFreeFeature4: "Простые тесты",
    pricingFreeFeature5: "Доступ с мобильных и веб",
    pricingFreeButton: "Начать бесплатно",
    pricingPremiumTitle: "Премиум-доступ",
    pricingPremiumPrice: "15000₸",
    pricingPremiumDesc: "Пожизненный доступ ко всем возможностям",
    pricingPremiumFeature1: "Неограниченные истории",
    pricingPremiumFeature2: "Все предметы и темы",
    pricingPremiumFeature3: "Премиум HD аудио и видео",
    pricingPremiumFeature4: "Интерактивные тесты и игры",
    pricingPremiumFeature5: "Отслеживание прогресса",
    pricingPremiumFeature6: "Офлайн-загрузки",
    pricingPremiumFeature7: "Приоритетная поддержка",
    pricingPremiumButton: "Купить Премиум",
    pricingDiscountBadge: "Скидка для новых",
    pricingDiscountText: "Ограниченное предложение для новых пользователей",
    pricingOriginalPrice: "25000₸",
    pricingFamilyTitle: "Семейное приключение",
    pricingFamilyPrice: "999₽",
    pricingFamilyDesc: "Идеально для семей и домашнего обучения",
    pricingFamilyFeature1: "Все, что в Премиум",
    pricingFamilyFeature2: "До 6 семейных профилей",
    pricingFamilyFeature3: "Родительский контроль и отчеты",
    pricingFamilyFeature4: "Контент по возрасту",
    pricingFamilyFeature5: "Семейные учебные цели",
    pricingFamilyFeature6: "Руководство по домашнему обучению",
    pricingFamilyFeature7: "Приоритетная семейная поддержка",
    pricingFamilyButton: "Начать семейную подписку",
    pricingMoneyBack: "Все планы включают 30-дневную гарантию возврата денег",
    pricingGuarantee1: "Отмена в любое время",
    pricingGuarantee2: "Без комиссий за установку",
    pricingGuarantee3: "Безопасные платежи",
    pricingEducatorsTitle: "Для преподавателей и школ",
    pricingEducatorsDesc:
      "Специальные цены для учителей и учебных заведений",
    pricingEducatorsButton: "Получить скидку для преподавателя",
    pricingPopularBadge: "Самый популярный",
    // Testimonials
    testimonialsTitle: "Истории, которые вдохновляют",
    testimonialsSubtitle:
      "Узнайте, как Fibonacci меняет опыт обучения для учеников и преподавателей",
    testimonial1Name: "Г-жа Сара Джонсон",
    testimonial1Role: "Учитель истории 8-го класса",
    testimonial1Quote:
      "Мои ученики теперь с восторгом ходят на уроки истории! История о Римской империи их полностью захватила.",
    testimonial2Name: "Д-р Роберт Чен",
    testimonial2Role: "Профессор философии",
    testimonial2Quote:
      "Наконец-то способ сделать философию доступной для подростков. История о Сократе была гениальной!",
    testimonial3Name: "Лиза Мартинес",
    testimonial3Role: "Мама ученика 7-го класса",
    testimonial3Quote:
      "Моя дочь от ненависти к географии перешла к просьбам рассказать больше историй о разных странах!",
    // CTA
    ctaTitle: "Готовы изменить обучение?",
    ctaSubtitle:
      "Присоединяйтесь к тысячам преподавателей и студентов, которые делают обучение волшебным с Fibonacci",
    ctaInputPlaceholder: "Введите ваш адрес электронной почты",
    ctaButton: "Присоединиться к списку ожидания",
    ctaDisclaimer: "Получите ранний доступ и эксклюзивные обновления. Никакого спама, никогда.",
    // Footer
    footerSlogan:
      "Делаем гуманитарное образование волшебным с помощью историй, созданных ИИ.",
    footerProductTitle: "Продукт",
    footerProductLink1: "Возможности",
    footerProductLink2: "Как это работает",
    footerProductLink3: "Цены",
    footerProductLink4: "Истории",
    footerEducatorsTitle: "Для преподавателей",
    footerEducatorsLink1: "Инструменты для класса",
    footerEducatorsLink2: "Учебное пособие",
    footerEducatorsLink3: "Ресурсы для учителей",
    footerEducatorsLink4: "Профессиональное развитие",
    footerSupportTitle: "Поддержка",
    footerSupportLink1: "Центр помощи",
    footerSupportLink2: "Связаться с нами",
    footerSupportLink3: "Политика конфиденциальности",
    footerSupportLink4: "Условия использования",
    footerCopyright: "© 2025 Fibonacci. Все права защищены. Сделано с ❤️ для учеников во всем мире.",
    // Register Page
    registerTitle: "Создать аккаунт",
    registerSubtitle: "Введите свои данные, чтобы начать работу с Fibonacci",
    registerEmailLabel: "Электронная почта",
    registerEmailPlaceholder: "john@example.com",
    registerPasswordLabel: "Пароль",
    registerButton: "Создать аккаунт",
    registerLoginPrompt: "Уже есть аккаунт?",
    registerLoginLink: "Войти",
    registerUsernameLabel: "Имя пользователя",
    registerUsernamePlaceholder: "johndoe",
    registerDisplayNameLabel: "Отображаемое имя (необязательно)",
    registerDisplayNamePlaceholder: "Джон Доу",
    registerConfirmPasswordLabel: "Подтвердите пароль",
    registerGoogleButton: "Зарегистрироваться через Google",
    registerCreatingAccount: "Создание аккаунта...",
    // Login Page
    loginTitle: "С возвращением",
    loginSubtitle: "Введите свои данные для доступа к вашему аккаунту",
    loginButton: "Войти",
    loginRegisterPrompt: "Нет аккаунта?",
    loginRegisterLink: "Зарегистрироваться",
    loginEmailLabel: "Электронная почта",
    loginEmailPlaceholder: "john@example.com",
    loginPasswordLabel: "Пароль",
    loginForgotPassword: "Забыли пароль?",
    loginGoogleButton: "Войти через Google",
    loginSigningIn: "Вход в систему...",
    // Feedback Form
    feedbackEmailPlaceholder: "Email (необязательно)",
    feedbackMessagePlaceholder: "Ваш отзыв, идеи или ошибки...",
    feedbackSending: "Отправка...",
    feedbackThankYou: "Спасибо!",
    feedbackSendButton: "Отправить отзыв",
    feedbackError: "Не удалось отправить. Попробуйте позже.",
    orContinueWith: "Или продолжить с",
  },
};

export default translations; 
