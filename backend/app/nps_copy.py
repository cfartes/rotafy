"""User-approved service copy and equivalent travel wording."""

SCORE = {
    "service": "Sua opinião é fundamental para continuarmos evoluindo! 🚀\n\nEm uma escala de 0 a 10, o quanto você recomendaria o nosso atendimento para um amigo ou familiar?\n\n(Sendo 0 para 'não recomendaria' e 10 para 'com certeza recomendaria')\n\nResponda apenas com o número da sua nota.",
    "trip": "Esperamos que sua viagem tenha deixado boas lembranças! 💙\n\nSua opinião é fundamental para continuarmos criando experiências cada vez melhores! 🚀\n\nEm uma escala de 0 a 10, o quanto você recomendaria viajar com a {company} para um amigo ou familiar?\n\n(Sendo 0 para 'não recomendaria' e 10 para 'com certeza recomendaria')\n\nResponda apenas com o número da sua nota.",
}
PROMOTER = {
    "service": "Uau, ficamos extremamente felizes com a sua nota! 🎉\n\nSaber que superamos suas expectativas nos enche de orgulho. Muito obrigado pela confiança e parceria de sempre! Tenha um dia incrível! 💙",
    "trip": "Uau, ficamos extremamente felizes com a sua nota! 🎉\n\nSaber que fizemos parte de uma boa experiência nos enche de alegria. Muito obrigado pela confiança e companhia! Esperamos viajar com você novamente em breve! 💙",
}
PASSIVE = {
    "service": "Muito obrigado pelo seu feedback! 😊\n\nQueremos que sua experiência seja sempre impecável. Se tiver qualquer sugestão sobre o que podemos fazer para transformar seu próximo atendimento em uma nota 10, conta para a gente!",
    "trip": "Muito obrigado pelo seu feedback! 😊\n\nQueremos que cada viagem seja especial. O que podemos melhorar para transformar sua próxima experiência com a gente em uma nota 10?",
}
DETRACTOR = {
    "service": "Poxa, lamentamos muito saber disso! 😔\n\nPedimos desculpas se o nosso atendimento não atendeu às suas expectativas. Para podermos corrigir e melhorar, o que poderíamos ter feito de diferente hoje?\n\nSua resposta será enviada diretamente para a nossa equipe de qualidade.",
    "trip": "Poxa, lamentamos muito saber disso! 😔\n\nPedimos desculpas se a viagem não atendeu às suas expectativas. Para podermos corrigir e melhorar, o que poderíamos ter feito de diferente nessa experiência?\n\nSua resposta será enviada diretamente para a nossa equipe de qualidade.",
}


def invitation(kind, company, trip_name=None):
    question = SCORE[kind].format(company=company)
    context = f"Viagem: {trip_name}\n\n" if kind == "trip" and trip_name else ""
    return (
        question,
        context
        + question
        + "\n\nVocê tem 24 horas para responder. Se preferir não participar, envie PULAR ou ENCERRAR.",
    )


def feedback(kind, score):
    return (
        PROMOTER[kind]
        if score >= 9
        else PASSIVE[kind]
        if score >= 7
        else DETRACTOR[kind]
    )
