"""Starter directory: real Georgian-language shows with public RSS feeds (found via Apple's podcast search for GE).

Indexing a public feed is what every podcast app does; audio stays on the publisher's host and each page links
back. Publishers can claim their show on SIVRCE or ask for removal. Keep this list to shows that are active,
public and relevant to an audience that works, learns and builds things in Georgia.
"""
STARTER = [
    # საქმე და ბიზნესი
    {'feed': 'https://anchor.fm/s/cd87b90/podcast/rss', 'topic': 'work', 'apple_id': '1515364476', 'featured': True},   # Marketer.ge Podcast
    {'feed': 'https://anchor.fm/s/45dc324c/podcast/rss', 'topic': 'work'},                                              # შენი აუდიო სივრცე (1tv)
    {'feed': 'https://anchor.fm/s/10626f960/podcast/rss', 'topic': 'growth'},                                           # ბალანსი
    # მეცნიერება და ტექნოლოგია
    {'feed': 'https://feed.podbean.com/nextonge/feed.xml', 'topic': 'science', 'featured': True},                       # შემდეგი პოდკასტი (NEXT.On.ge)
    {'feed': 'https://feeds.soundcloud.com/users/soundcloud:users:397992282/sounds.rss', 'topic': 'science'},           # მეცნიერება ყველასათვის
    {'feed': 'https://feeds.simplecast.com/aRzXUUAp', 'topic': 'science'},                                              # ტექ თოქი
    {'feed': 'https://anchor.fm/s/5f1de700/podcast/rss', 'topic': 'science'},                                           # ორჯერ ორი
    {'feed': 'https://anchor.fm/s/10fa4aa28/podcast/rss', 'topic': 'science'},                                          # ცარიელი აზრები / Empty Thoughts
    # საზოგადოება
    {'feed': 'https://anchor.fm/s/ee8404d8/podcast/rss', 'topic': 'society', 'featured': True},                         # პირადი საქმე (64 Project)
    {'feed': 'https://www.radiotavisupleba.ge/podcast/?zoneId=18711', 'topic': 'society'},                              # ნიკოს პოდკასტი
    {'feed': 'https://www.radiotavisupleba.ge/podcast/?zoneId=22405', 'topic': 'society'},                              # შინ — უცხოეთში
    {'feed': 'https://anchor.fm/s/37c9dbdc/podcast/rss', 'topic': 'society'},                                           # სოციალური სამართლიანობის ცენტრი
    {'feed': 'https://anchor.fm/s/edc6a7e4/podcast/rss', 'topic': 'society'},                                           # GZAZE • გზაზე
    {'feed': 'https://anchor.fm/s/eb4df274/podcast/rss', 'topic': 'society'},                                           # Duty Free Talks
    {'feed': 'https://anchor.fm/s/ede6308c/podcast/rss', 'topic': 'growth'},                                            # პრინციპში ყველაფერზე
    {'feed': 'https://feeds.async.com/0522fdef-ade3-4bbf-9f6f-770d62ed7c18.rss', 'topic': 'growth'},                    # Tbilini Podcast
    # კულტურა და ისტორია
    {'feed': 'https://www.radiotavisupleba.ge/podcast/?zoneId=21364', 'topic': 'culture'},                              # ასათიანის კუთხე
    {'feed': 'https://www.radiotavisupleba.ge/podcast/?zoneId=22605', 'topic': 'culture'},                              # ლიტერატურული პოდკასტი „წიგნები“
    {'feed': 'https://feed.podbean.com/napoleontalk/feed.xml', 'topic': 'culture'},                                     # საუბრები ნაპოლეონზე
    {'feed': 'https://anchor.fm/s/78352f28/podcast/rss', 'topic': 'culture'},                                           # დირექცია / Film Office
    # ჯანმრთელობა
    {'feed': 'https://anchor.fm/s/10f57c050/podcast/rss', 'topic': 'growth'},                                           # Georgian Medical Journal Podcast
]
