from app.services.generation.people_context import PeopleContext, PeopleFaceContext


def test_anonymized_prompt_hint_basic():
    face1 = PeopleFaceContext(
        person_name="Konrad",
        bounding_box_x1=10,
        bounding_box_y1=10,
        bounding_box_x2=20,
        bounding_box_y2=20,
        image_width=100,
        image_height=100
    )
    face2 = PeopleFaceContext(
        person_name="Sylwek Sokół",
        bounding_box_x1=80,
        bounding_box_y1=80,
        bounding_box_x2=90,
        bounding_box_y2=90,
        image_width=100,
        image_height=100
    )
    
    context = PeopleContext(
        names=["Konrad", "Sylwek Sokół"],
        faces=[face1, face2],
        prompt_hint="Immich identified these people in the source photo: Konrad, Sylwek Sokół. Face positions: Konrad is in the upper left; Sylwek Sokół is in the lower right."
    )
    
    anonymized = context.anonymized_prompt_hint()
    
    assert "Konrad" not in anonymized
    assert "Sylwek" not in anonymized
    assert "Sokół" not in anonymized
    assert "person 1" in anonymized
    assert "person 2" in anonymized
    assert "person 1 is in the upper left" in anonymized
    assert "person 2 is in the lower right" in anonymized
    
    # Ensure original fields are untouched
    assert context.prompt_hint == "Immich identified these people in the source photo: Konrad, Sylwek Sokół. Face positions: Konrad is in the upper left; Sylwek Sokół is in the lower right."
