from django.db import transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django_ai_assistant.models import Article, FAQ
from django_ai_assistant.vector_store import rebuild_agent_index

@receiver([post_save, post_delete], sender=Article)
def update_agent_articles(sender, instance, **kwargs):
    if not instance.agent:
        return
    # Use on_commit to avoid blocking DB transaction and "database is locked" errors
    transaction.on_commit(lambda: reindex_agent(instance.agent))

@receiver([post_save, post_delete], sender=FAQ)
def update_agent_faqs(sender, instance, **kwargs):
    if not instance.agent:
        return
    transaction.on_commit(lambda: reindex_agent(instance.agent))

def reindex_agent(agent):
    """
    Gathers all published Articles and FAQs for the agent and rebuilds the index.
    """
    texts = []
    metadatas = []

    # Process Articles
    articles = agent.articles.filter(is_published=True)
    for article in articles:
        text = f"Title: {article.title}\nContent: {article.content}"
        texts.append(text)
        metadatas.append({
            "source": "article", 
            "id": article.id, 
            "title": article.title
        })

    # Process FAQs
    faqs = agent.faqs.filter(is_published=True)
    for faq in faqs:
        text = f"Question: {faq.question}\nAnswer: {faq.answer}"
        texts.append(text)
        metadatas.append({
            "source": "faq", 
            "id": faq.id, 
            "question": faq.question
        })


    if texts:
        try:
            rebuild_agent_index(agent.name, texts, metadatas)
        except Exception as e:
            print(f"Error rebuilding index for agent {agent.name}: {e}")
    else:
        # TODO: Handle clear index if empty
        pass
